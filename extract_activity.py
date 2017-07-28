# coding:utf-8

import logging
import re

LOG_FORMAT = '%(asctime)s - %(filename)s[line:%(lineno)d] - %(threadName)s - %(levelname)s: %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


def manifest_extract(filename):
    """
    提取aapt dump的AndroidManifest.xml中的声明为Launcher的Activity信息
    """
    sp = re.compile(r'\s+')     # 空白模式，用于求一行前面的空格数
    ap = re.compile(r'E: activity(-alias)? \(line=\d+\)')    # activity pattern
    np = re.compile(r'A: android:name\(0x\d+\)="([^ ]+)"')   # name属性pattern
    cp = re.compile(r'A: android:name\(0x\d+\)="android.intent.category.LAUNCHER"')     # category为LAUNCHER的pattern，该模式也会满足‘np’

    activitys = []
    with open(filename, 'r') as f:

        entered = False
        space_width = 0
        name = None

        line = f.readline()
        logging.debug(line)
        while line:

            if not entered:
                search = ap.search(line)        # 匹配Activity头标签
                if search:
                    logging.debug('entered activity :%s' % line)
                    logging.debug('space width :%d' % search.start())
                    entered = True
                    space_width = search.start()
            else:
                search = sp.search(line)        # 匹配该行的头部空白数量
                if search.end() > space_width:  # 若空白数量多余Activity标签的空白数量，说明是子元素
                    logging.debug('child line : %s' % line)

                    search = np.search(line)
                    if search and name is None:     # Activity的name属性，只在第一次赋值，因为子元素可能也包含该属性
                        name = search.group(1)
                        logging.debug('save name : %s' % name)

                    search = cp.search(line)        # category是LAUNCHER
                    if search:
                        activitys.append(name)
                        logging.debug('append name : %s' % name)

                else:       # 已经跳出前一个正在处理的Activity标签，恢复状态标志，重新处理该行
                    logging.debug('exit activity : %s' % name)
                    entered = False
                    name = None
                    continue    # 重新处理当前行，直接continue

            line = f.readline()

    print(activitys)
