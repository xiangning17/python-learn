# Word文档以及PDF文档关键词提取
**已完成独立文档的解析，关键词提取**

**主要工作有：**

## 解析PDF文档
### 1. 使用pdfminer解析文档
### 2. 计算字体大小。因为pdfminer中得到的文字对象只能得到固定宽高，因此以行高近似字体大小

## 解析word文档
### 1. 对于老版本的doc文档，先将之转换成docx文档。使用ubuntu自带liboffice软件的soffice命令。
> soffice --headless --convert-to docx xxx.doc

### 2. 使用docx解析文档，得到文字段落列表

    doc = docx.Document(docName)
    paras = doc.paragraphs

### 3. 解析表格以及嵌套表格中的段落

对于从doc获取的所有table，使用**extend_paras_from_table**进行处理

    for table in doc.tables:  # 添加表格中的段落
        extend_paras_from_table(table)

**extend_paras_from_table**定义如下，递归地从单元格中获取段落并拼接到paras中

     def extend_paras_from_table(table):
         for i in range(len(table.rows)):
             for j in range(table._column_count):
                 cell = table.cell(i, j)

                 tc = cell._tc
                 if tc.left != j or tc.top != i:  # 忽略融合的单元格
                     continue
 
                 paras.extend(cell.paragraphs)
                 for t in cell.tables:
                     extend_paras_from_table(t)  # 添加表格单元中的嵌套表格

### 4. 处理段落中的文字,对于每个run提取其size与bold属性，以及text

    for run in p.runs:  # 处理同一段中不同样式的文字
        if run._r and run._r.rPr:  # 如果有内嵌的字体大小/粗体等控制，则更新相应的值。
        
            if run._r.rPr.sz_val:
                size = run._r.rPr.sz_val / 6350
            if run._r.rPr.b is not None:  # r._r.rPr.b的‘b’所属类定制了bool返回值，因此必须使用‘is not None’判断！
                bold = run._r.rPr.b.val

        if bold:
            size *= 1.5
        text = run.text
        
### 5. 将相同size的text放进weight_category字典的以该size为key的列表中
    if size in weight_category:
        weight_category[size].append(text)
    else:
        weight_category[size] = [text]
        
## 使用Jieba结合spacy（处理英文）进行词频统计

### 对weight_category中不同size(权重)的段落分别进行处理;对段落中的英文，由于Jieba只能给出‘eng’标注其为英语，因此使用spacy再进行进一步处理
    word_freq = {}
    nlp = spacy.load('en_default')  # 使用spacy处理英文
    
    for weight, ps in weight_paras.items():
        weight = int(weight)
        logging.info('process weight-%d, length=%d' % (weight, len(ps)))

        for p in ps:
            logging.debug('process :%s' % p)
            words = pseg.cut(p)     # 使用Jieba的词性标注模块进行处理
            engs = []               # 统计出段落中的英文，进行后续的spacy处理

            for word in words:
                flag = word.flag
                word = word.word
                if not flag.startswith('n') and not flag == 'eng':  # 只处理名词词性与英语词汇
                    continue

                words_count += 1

                if flag == 'eng':   # 若是英语，则添加到eng列表，待后续处理
                    eng_count += 1
                    engs.append(word)
                else:               # 中文根据权重进行累加词频
                    if word in word_freq:
                        word_freq[word] += 1 * weight
                    else:
                        word_freq[word] = 1 * weight

            english_process(nlp, u' '.join(engs), weight, word_freq)
            
english_process函数定义如下,还是只取名词性词语，并进行词干化后再记录

    def english_process(nlp, article, weight, word_freq):
        doc = nlp(article)
        for token in doc:
            if not token.tag_.startswith('NN'):  # 只取名词
                continue
    
            word = token.lemma_  # 词干化
            if word in word_freq:
                word_freq[word] += 1 * weight
            else:
                word_freq[word] = 1 * weight