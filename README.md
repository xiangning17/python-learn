# python-learn
学习python过程中的一些小练习

##任务二：每天定时从web服务器同步cts目录下所有文件到本地。
**已实现目标与相应使用的工具库：**


目标|工具
---|:---:
获取cts网页并解析其下所有文件以及子目录的信息。包括文件名（包含路径），文件下载url，文件修改时间| urllib，BeautifulSoup
保存文件的修改信息到本地 | sqlite
比较之前本地保存的文件修改时间与服务器获取的文件修改时间，若不同则（重新）下载该文件到本地 | urllib.retrieve
定时任务功能，在每天定时启动任务| apscheduler
为加快同步效率增加多线程处理| threading， Queue