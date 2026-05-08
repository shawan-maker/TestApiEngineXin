"""定义工具函数，在前后置中使用"""
import base64
import time
import rsa
from faker import Faker

fk = Faker(locale='zh_CN')

def random_mobile():
    """生成随机手机号"""
    return fk.phone_number()

def random_name():
    """生成随机姓名"""
    return fk.name()

def random_ssn():
    """生成随机身份证号"""
    return fk.ssn()

def random_address():
    """生成随机地址"""
    return fk.address()

def random_city():
    """生成随机一个城市名"""
    return fk.city()

def random_company():
    """生成随机公司名"""
    return fk.company()

def postcode():
    """生成随机城市的邮编"""
    return fk.postcode()

def random_email():
    """生成随机邮箱"""
    return fk.email()

def random_date():
    """生成随机日期"""
    return fk.date()

def random_datetime():
    """生成随机时间"""
    return fk.date_time()

def get_timestamp():
    """获取当前时间戳"""
    return int(time.time())

def random_ipv4():
    """生成随机IPv4"""
    return fk.ipv4()

def base64_encode(data):
    """base64编码"""
    return base64.b64encode(data.encode('utf-8')).decode('utf-8')

def md5_encode(data):
    """md5编码"""
    from hashlib import md5
    new_md5 = md5()
    new_md5.update(data.encode('utf-8'))
    return new_md5.hexdigest()

def rsa_encrypt(msg, server_pub):
    """rsa加密"""
    msg = msg.encode('utf-8')
    pub_key = server_pub.encode('utf-8')
    public_key = rsa.PublicKey.load_pkcs1_openssl_pem(pub_key)
    crypt_msg = rsa.encrypt(msg, public_key)
    cipher_text = base64.b64encode(crypt_msg).decode('utf-8')
    return cipher_text