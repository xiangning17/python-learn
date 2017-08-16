# coding utf-8
import glob
import os
import smtplib
import traceback
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header

import logging


def mail():
    sender = 'xiangning17@foxmail.com'
    receivers = ['xiangning17@foxmail.com']  # 接收邮件，可设置为你的QQ邮箱或者其他邮箱

    # 三个参数：第一个为文本内容，第二个 plain 设置文本格式，第三个 utf-8 设置编码
    # message = MIMEText('Python 邮件发送测试...', 'plain', 'utf-8')
    message = MIMEMultipart()
    message['From'] = Header("菜鸟教程", 'utf-8')
    message['To'] = Header("测试", 'utf-8')
    message['Subject'] = Header('Python SMTP 发送可变张数无分隔嵌入图片示例邮件测试', 'utf-8')

    # send images
    imgs = MIMEMultipart('related')     # 'related'用于html嵌入图片，但attach时必须先attach html内容，然后attach图片

    html = MIMEText('', "html", "utf-8")    # 先内容留空，以便后续动态添加图片
    imgs.attach(html)

    ids = []
    for img_name in glob.glob("data" + os.sep + "*.png"):
        # 二进制模式读取图片
        with open(img_name, "rb") as f:
            img = MIMEImage(f.read())

            # 定义图片ID
            base_name = os.path.basename(img_name)
            img_id = base_name[:base_name.rfind(".")]
            print(img_id)
            ids.append(img_id)

            img.add_header("Content-ID", img_id)
            imgs.attach(img)

    cont = '这是一些图片<br>'
    for img_id in ids:
        cont += '<img src="cid:%s"/>' % img_id
    charset = html.get_charset().body_encode(cont)  # base64编码
    html.set_payload(charset)
    print(html)

    message.attach(imgs)

    try:
        smtp_obj = smtplib.SMTP('xxx', 587)
        smtp_obj.login('xxx', 'xxx')
        smtp_obj.sendmail(sender, receivers, message.as_string())
        logging.debug("邮件发送成功")
    except smtplib.SMTPException:
        logging.debug("Error: 无法发送邮件")
        traceback.print_exc()
