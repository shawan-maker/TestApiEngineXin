"""套件级共享变量存储（跨 TestRunner 实例）。

设计目的：
  同一个套件内的多个用例各自创建独立的 TestRunner 实例，
  但需要共享变量（save_env_variable / save_global_variable 设置的值）。
  本模块提供类级别的注册表，用 run_id 关联同一套件的所有实例。

线程安全：
  所有 dict 写操作通过 threading.Lock 保护，支持并行用例场景。

生命周期：
  平台层在套件开始前调用 register_run()，结束后调用 unregister_run()。
  cleanup_stale() 兜底清理异常中断导致的残留。
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Set


@dataclass
class RunStore:
    """单次套件运行的共享变量存储。

    envs:          套件级累积环境变量（含初始基线 + 运行中写入）
    debug_updates: 需要持久化到 DB 的全局变量变更队列
    temp_keys:     标记哪些 key 是 save_env_variable 写入的（区分 temp 与 global）
    lock:          保护并发写操作
    created_at:    注册时间戳（用于 TTL 清理）
    """
    envs: dict = field(default_factory=dict)
    debug_updates: dict = field(default_factory=dict)
    temp_keys: Set[str] = field(default_factory=set)
    lock: threading.Lock = field(default_factory=threading.Lock)
    created_at: float = field(default_factory=time.time)


class RunRegistry:
    """类级别注册表：run_id → RunStore。

    串行场景：后续用例可读到前面用例设置的变量。
    并行场景：lock 保护 dict 操作，last-write-wins。
    """
    _stores: Dict[str, RunStore] = {}
    _registry_lock = threading.Lock()

    @classmethod
    def register(cls, run_id: str, initial_envs: dict) -> RunStore:
        """注册套件运行，创建共享存储。"""
        with cls._registry_lock:
            store = RunStore(envs=dict(initial_envs or {}))
            cls._stores[run_id] = store
            return store

    @classmethod
    def get(cls, run_id: str) -> Optional[RunStore]:
        """获取指定运行的共享存储。"""
        return cls._stores.get(run_id)

    @classmethod
    def unregister(cls, run_id: str) -> None:
        """清理指定运行的共享存储。务必在 finally 中调用。"""
        with cls._registry_lock:
            cls._stores.pop(run_id, None)

    @classmethod
    def cleanup_stale(cls, max_age_seconds: float = 3600) -> int:
        """清理超时的残留 store（防止异常中断导致内存泄漏）。

        :param max_age_seconds: 超时阈值（秒），默认1小时
        :return: 清理数量
        """
        now = time.time()
        with cls._registry_lock:
            stale = [
                rid for rid, s in cls._stores.items()
                if now - s.created_at > max_age_seconds
            ]
            for rid in stale:
                cls._stores.pop(rid, None)
            return len(stale)
