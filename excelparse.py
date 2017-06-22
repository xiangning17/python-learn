#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 任务一：从网站下载存储项目翻译的Excel表格并统计缺失的翻译

from urllib import urlretrieve
import xlrd


def count_empty_trans():
    """count the empty trans for some strings.xls"""
    url = "http://172.26.32.15/gitweb-mtk6735/" \
          "?p=device/jrdchz/common/perso/wlanguage.git;" \
          "a=blob;f=src/strings.xls;h=2e9f14a07c616e3b69714a5afa2a798f0479883f;" \
          "hb=b9a742a960f11f311c13e1cec219027240b87d4d"
    filename = "./string.xls"
    urlretrieve(url, filename)
    print "download finish!"

    data = xlrd.open_workbook(filename)
    trans_sheet = data.sheet_by_name("MESSAGE")
    titles = trans_sheet.row_values(0)
    trans_start_index = 8   # trans content start from column "I", "English_GB"
    count_row = 0   # recode the count of row who has empty trans.
    count_all = 0   # recode the count of empty trans.

    for i in range(1, trans_sheet.nrows):
        row = trans_sheet.row_values(i)
        empty_cells = []
        for j in range(trans_start_index, trans_sheet.ncols):
            if len(row[j].strip()) == 0:    # for u"", isspace always return True, so change the way of judge empty str.
                empty_cells.append(titles[j])

        if len(empty_cells) > 0:
            print row[0], "with %d empty trans :" % len(empty_cells), empty_cells
            count_row += 1
            count_all += len(empty_cells)
    print "empty trans occur row count are ", count_row
    print "all empty trans count are ", count_all

if __name__ == '__main__':
    count_empty_trans()


