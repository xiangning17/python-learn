# encoding: utf-8

import pygtk
import gtk

import sqlite3
from traceback import print_exc

pygtk.require('2.0')


class User(object):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "User(%s, %s)" % (self._name, )

    __repr__ = __str__

    @classmethod
    def get_user(cls, name, pwd):   # 通过用户名和密码查询用户记录并返回对应的User实体
        con = cls._open_db()
        cursor = con.cursor()
        print("get user : %s, %s" % (name, pwd))
        cursor.execute("SELECT * FROM user WHERE name=? AND pwd=?", (unicode(name, "utf-8"), unicode(pwd, "utf-8")))
        result = cursor.fetchone()
        print "get by name : ", result
        if result:
            return User(result[1])

    @classmethod
    def insert(cls, name, pwd):
        con = cls._open_db()
        try:
            con.execute("INSERT INTO user (name, pwd) VALUES (?, ?)", (unicode(name, "utf-8"), unicode(pwd, "utf-8")))
            con.commit()
        except Exception as e:      # 若该用户名已存在，则会抛出异常，捕获并返回False表明添加用户失败
            print_exc()
            return False

        return True

    _con = None

    @classmethod
    def _open_db(cls):

        if cls._con is None:        # 若数据库连接还未创建，则创建
            con = sqlite3.connect("./user.db")
            con.execute(
                "CREATE TABLE IF NOT EXISTS user ("
                "_id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "name TEXT UNIQUE NOT NULL,"
                "pwd TEXT NOT NULL )"
            )
            con.commit()

            cls._con = con

        return cls._con


class LoginWindow(gtk.Window):

    def __init__(self):
        super(LoginWindow, self).__init__()
        self.set_title("登陆")
        self.set_size_request(300, 250)
        self.set_border_width(8)
        self.set_position(gtk.WIN_POS_CENTER)

        align = gtk.Alignment(0.5, 0.3, 0, 0)

        vbox = gtk.VBox(False, 5)

        # 标题
        welcome = gtk.Label()
        welcome.set_markup("<span font_desc=\"20\" foreground=\"#0000FF\">欢迎使用</span>")

        vbox.pack_start(welcome, False, False, 10)  # 添加标题到垂直Box中，设置padding（上下的间隔）为10

        # 账号行
        user_box = gtk.HBox(False, 10)
        label_user = gtk.Label(u"账 号")
        entry_user = gtk.Entry()
        self.entry_user = entry_user
        user_box.add(label_user)
        user_box.add(entry_user)

        vbox.add(user_box)      # 添加账号行到垂直Box

        # 密码行
        pwd_box = gtk.HBox(False, 10)
        label_pwd = gtk.Label(u"密 码")
        entry_pwd = gtk.Entry()
        entry_pwd.set_visibility(False)
        self.entry_pwd = entry_pwd
        pwd_box.add(label_pwd)
        pwd_box.add(entry_pwd)

        vbox.add(pwd_box)       # 添加密码行到垂直Box

        # 按钮行
        btn_box = gtk.HBox(True, 20)

        btn_register = gtk.Button("注册")
        btn_register.connect("clicked", self.on_register_clicked)   # 注册按钮的点击事件
        btn_login = gtk.Button("登陆")
        btn_login.connect("clicked", self.on_login_clicked)         # 登陆按钮的点击事件

        btn_box.add(btn_register)
        btn_box.add(btn_login)
        vbox.pack_start(btn_box, True, True, 30)        # 添加按钮行到垂直Box

        align.add(vbox)

        self.add(align)

        self.connect("destroy", gtk.main_quit)
        self.show_all()

    def main(self):
        gtk.main()

    def on_register_clicked(self, btn, *data):
        name = self.entry_user.get_text()
        pwd = self.entry_pwd.get_text()
        if User.insert(name, pwd):
            self.show_msg("恭喜你，注册成功！", gtk.MESSAGE_INFO)
        else:
            self.show_msg("用户<span font_desc=\"34\" color=\"#0000FF\">%s</span>已存在！" % name, gtk.MESSAGE_ERROR)

    def on_login_clicked(self, btn, *data):
        name = self.entry_user.get_text()
        pwd = self.entry_pwd.get_text()
        user = User.get_user(name, pwd)
        if user:
            self.show_msg("用户<span font_desc=\"34\" color=\"#0000FF\">%s</span>登陆成功！" % name, gtk.MESSAGE_INFO)
        else:
            self.show_msg("用户名或者密码错误！", gtk.MESSAGE_ERROR)

    def show_msg(self, msg, type):
        message = gtk.MessageDialog(type=type, buttons=gtk.BUTTONS_OK)
        message.set_markup(msg)
        message.run()
        message.destroy()


if __name__ == '__main__':
    LoginWindow().main()

