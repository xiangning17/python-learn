# python-learn
学习python过程中的一些小练习

##任务二 - 改：每天定时从web服务器同步cts目录下所有文件到本地。

**主要改进有：**
* 使用文件本身的modify time属性存储从网站上同步得到的文件修改时间，省略了使用数据库或者pickleDB等数据持久化方式。
  具体操作是用“os.utime()”方法进行写入。
* 改进多线程执行逻辑，将多线程执行逻辑分离成单独的类，在主文件中使用装饰器为同步任务添加多线程执行功能。
  同时，多线程执行也可参考其他三方库的实现，如ThreadPoolExecutor或者tomorrow。
* 使用系统提供的cron定时任务程序实现定时任务，在终端执行“crontab -e”，然后写入配置该任务
  在每天18点执行。
  > 0 18 * * * python ~/PycharmProjects/python-learn/cts_sync.py
  
改进后，主体代码减少了一半到，逻辑更清晰。