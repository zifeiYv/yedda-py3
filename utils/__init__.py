# -*- coding: utf-8 -*-
def auto_tagging(tagged_str: str, new_str: str) -> str:
    """根据标注的文本，获取其中的实体词及标签，对后续的未标注文本进行
    自动标注。

    :param tagged_str: 已经标注的文本
    :param new_str: 未标注的文本
    :return:
    """
    entity, entity_type = tagged_str.strip('[@]*').split('#')

    # 对剩下的字符串按照标点符号进行切分，只标注最近的20个句子
    v = 20
    # 先按换行符进行分段
    para_list = new_str.split('\n')
    # 遍历每一段，并初始化一个计数器，达到20次后不再继续
    counter = 0
    new_tagged = ''
    for idx in range(len(para_list)):
        p = para_list[idx]
        if new_tagged:  # 不是第一个段落
            new_tagged += '\n'
        if not p:
            continue
        # else p有字符
        if counter == v:
            # 如果达到最大的次数，则把剩下的段落拼接追加到new_tagged
            return new_tagged + '\n'.join(para_list[idx:])
        # 否则，开始分句，并进行识别
        sentences = p.split('。')
        for _idx in range(len(sentences)):
            s = sentences[_idx ]
            if not s:
                new_tagged += '。'
                continue
            else:
                if counter == v:
                    new_tagged += '。'.join(sentences[_idx:])
                    break
                new_tagged += s.replace(entity, tagged_str)
                counter += 1
    return new_tagged


if __name__ == '__main__':
    new_st = '当日新增治愈出院病例15例，解除医学观察的密切接触者288人，重症病例较前一日减少2例。\n\n当日新增治愈出院病例15例，解除医学观察的密切接触者288人，重症病例较前一日减少2例。\n'
    print(new_st)
    print(auto_tagging('[@新增治愈出院病例#Artifical*]', new_st))
