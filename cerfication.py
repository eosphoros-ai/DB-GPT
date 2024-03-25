# -*- encoding:utf-8 -*-
'''
@describe: 
@author: Li Anbang
@Create Date: 2024/3/22 下午2:20
'''
from OpenSSL import crypto, SSL


def generate_certificate(
        organization="PrivacyFilter",
        common_name="172.23.52.25:50000",
        country="NL",
        duration=(365 * 24 * 60 * 60),
        keyfilename="key.pem",
        certfilename="cert.pem"):
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 4096)

    cert = crypto.X509()
    cert.get_subject().C = country
    cert.get_subject().O = organization
    cert.get_subject().CN = common_name
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(duration)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha512')

    with open(keyfilename, "wt") as keyfile:
        keyfile.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8"))
    with open(certfilename, "wt") as certfile:
        certfile.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8"))

def second():
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, NoEncryption, Encoding
    from cryptography.hazmat.backends import default_backend
    import datetime

    # 生成密钥
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    # 填写证书信息
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"CN"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"fujian"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"Ningde"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"ATL"),
        x509.NameAttribute(NameOID.COMMON_NAME, u"172.23.52.25"),
    ])

    # 创建证书
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        # 证书有效期为 1 年
        datetime.datetime.utcnow() + datetime.timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName([x509.DNSName(u"172.23.52.25")]),
        critical=False,
    ).sign(key, hashes.SHA256(), default_backend())

    # 将密钥和证书写入文件
    with open("private_key.pem", "wb") as f:
        f.write(key.private_bytes(
            encoding=Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption()
        ))

    with open("certificate.pem", "wb") as f:
        f.write(cert.public_bytes(Encoding.PEM))

    print("私钥和证书已生成")


if __name__ == '__main__':
    second()
