# -*- coding: utf-8 -*-
"""
todo:
    2、增加取消标记的功能
"""
import tkinter as tk
import platform
from tkinter import font, filedialog, ttk, Button
from collections import deque
import os.path
from utils import auto_tagging, init_logger
import json
from utils.colors import color_mapping
import re

logger = init_logger()


class MyFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.title = "文本标注工具"
        self._os = platform.system().lower()
        self.parent = parent
        self.file_name = ""
        self.auto_tag = False
        self.history = deque(maxlen=20)  # 存储操作历史，最多存储20步
        self.content = ''
        self.no_sel_text = False
        # 初始的"按键-指令"映射关系
        self.press_cmd = {}
        self.all_keys = "abcdefghijklmnopqrstuvwxyz"
        self.all_tagged_strings = {}  # 存储所有标注的文本的索引，及其对应的快捷键
        # 存储解释快捷键对应含义的Entry的List
        self.entry_list = []
        # 存储快捷键名称的Label的List
        self.label_list = []
        # ShortCuts Label
        self.sc_lbl = None
        # 显示配置文件名称的下拉列表控件
        self.config_box = None
        self.key_color_mapping = {}

        self.frame_rows = 20  # 固定行数
        self.frame_cols = 5  # 固定列数
        self.schema = "BMES"  # 默认的标注模式
        self.config_file = "configs/default.config"
        self.former_cfg_file = self.config_file
        self.entity_re = r'\[\@.*?\#.*?\*\](?!\#)'  # 标注后的词语的正则表达式
        # configure color
        self.select_color = 'light salmon'  # 选中后的文本颜色
        self.word_style = "Courier"  # 待标注文本的字体类型
        self.word_size = 20  # 待标注文本的字体大小
        self.weight = "normal"  # 待标注文本的字体不必加粗

        self.parent.title(self.title)
        self.pack(fill=tk.BOTH, expand=True)

        for idx in range(self.frame_cols):
            self.columnconfigure(idx, weight=2)
        self.columnconfigure(self.frame_cols, weight=1)
        self.columnconfigure(self.frame_cols + 1, weight=1)
        for idx in range(self.frame_rows):
            self.rowconfigure(idx, weight=1)
        # 文档提示信息
        self.lbl = tk.Label(self, text="没有打开的文件，点按右侧「打开文件」按钮打开文件")
        self.lbl.grid(row=0, column=0, rowspan=1, sticky=tk.W, pady=4, padx=10)
        # 文档显示设置
        self.fnt = font.Font(family=self.word_style, size=self.word_size, weight=self.weight, underline=0)
        self.text = tk.Text(self, font=self.fnt, selectbackground=self.select_color,
                            bg='#F2F2F2', borderwidth=10)
        self.text.grid(row=1, column=0, columnspan=self.frame_cols,
                       rowspan=self.frame_rows,
                       padx=10,
                       sticky=tk.E + tk.W + tk.S + tk.N)
        # 为文档显示区添加纵向滚动条
        self.sb = tk.Scrollbar(self)
        self.sb.grid(row=1, column=self.frame_cols, rowspan=self.frame_rows, padx=0,
                     sticky=tk.E + tk.W + tk.S + tk.N)
        self.text['yscrollcommand'] = self.sb.set
        self.sb['command'] = self.text.yview

        lbl = tk.Label(self, text='功能区', foreground="blue", font=(self.word_style, 20, "bold"))
        lbl.grid(row=1, column=self.frame_cols + 1, sticky='w')

        btn = Button(self, text="打开文件", command=self.open_file, width=12)
        btn.grid(row=2, column=self.frame_cols + 1)

        self.format_btn = Button(self, text="格式化", command=self.format, width=12)
        self.format_btn.grid(row=2, column=self.frame_cols + 2, pady=4)

        btn = Button(self, text="导出", command=self.export, width=12)
        btn.grid(row=3, column=self.frame_cols + 2, pady=4)

        btn = Button(self, text="退出程序", bg='red', command=self.quit, width=12)
        btn.grid(row=4, column=self.frame_cols + 2, pady=4)

        if len(self.history) < 2:
            self.undo_btn = Button(self, text="撤销", bg='red', command=self.undo, width=12, state='disabled')
        else:
            self.undo_btn = Button(self, text="撤销", bg='red', command=self.undo, width=12)

        self.undo_btn.grid(row=3, column=self.frame_cols + 1, pady=4)

        # 展示光标位置信息（cursor position）
        self.cr_info = tk.Label(self, text=("row: %s\ncol: %s" % (1, 0)),
                                font=(self.word_style, 10, "bold"))
        self.cr_info.grid(row=self.frame_rows + 1, column=self.frame_cols + 2, pady=4)
        # 光标当前位置
        self.cr_psn = '1.0'

        # 此功能暂时不可用
        self.msg_lbl = tk.Label(self, text="", anchor='w')
        self.msg_lbl.grid(row=self.frame_rows + 1, column=0, sticky=tk.E + tk.W + tk.S + tk.N, pady=4, padx=10)

        # 在Text控件中按下不同的键，绑定对应的操作
        for press_key in self.all_keys:
            # 按下时，就进行标注
            self.text.bind(press_key, self.press_key_action)
            # 标注完成后，需要在释放所按键时删除输入的所按键的字符
            release = "<KeyRelease-" + press_key + ">"
            self.text.bind(release, self.release_key_action)
        # if self._os == 'darwin':
        #     self.text.bind('<Control-Key-z>', self.fallback_and_render)
        #     self.text.bind('<Control-Key-u>', self.undo)
        # else:
        #     self.text.bind('<Control-z>', self.fallback_and_render)
        #     self.text.bind('<Control-u>', self.undo)
        
        self.text.bind('<ButtonRelease-1>', self.button_release_1)
        self.set_shortcuts_layout()

    def button_release_1(self, event):
        """单击鼠标左键的操作"""
        self.cr_psn = self.text.index(tk.INSERT)
        logger.info(f"更新光标位置:{self.cr_psn}")
        index = self.cr_psn.split('.')
        self.cr_info.config(text=("row: %s\ncol: %s" % (index[0], index[1])))

    def open_file(self):
        logger.info('选择文件')
        ftps = [('all files', '.*'), ('text files', '.txt'), ('ann files', '.ann')]
        dlg = filedialog.Open(self, filetypes=ftps)
        fl = dlg.show()
        logger.info(f'文件名称:{fl}')
        if fl:
            # 删除text控件中的内容
            self.text.delete("1.0", tk.END)
            # 读取内容并插入text控件
            text = self.read_file(fl)
            self.text.insert(tk.END, text)
            # 更新显示的文件路径
            self.set_label("文件位置：" + fl)
            self.save_to_history(text)

    def read_file(self, file_name):
        f = open(file_name, "r")
        text = f.read()
        self.file_name = file_name
        return text

    def set_label(self, new_file):
        """更新Label控件的显示内容"""
        self.lbl.config(text=new_file)

    def update_cr_psn(self, cr_psn):
        """更新显示的光标位置信息"""
        psn = cr_psn.split('.')
        cursor_text = ("row: %s\ncol: %s" % (psn[0], psn[-1]))
        self.cr_info.config(text=cursor_text)

    def press_then_release(self, event):
        """定义「按下一个按键并释放后」的操作 todo"""
        self.press_key_action(event)

    def press_key_action(self, event):
        """按下一个键位时，对应的操作"""
        press_key = event.char.upper()
        logger.info(f'捕获按键：{press_key}')
        if press_key not in self.press_cmd:
            self.msg_lbl.config(text=f'无效的快捷键{press_key}')
            logger.info(f'无效的快捷键{press_key}')
            content, all_tagged_strings = self.fallback_action(act_msg=f'撤销键入{press_key}', delete_last=False)
            self.render_text(content, self.cr_psn)
            return
        content, sel_last, all_tagged_strings = self.tag_text(press_key)
        if not content:
            return
        self.content = content
        self.all_tagged_strings = all_tagged_strings
        # 此时暂不渲染，因为按下键时，已经在最后插入了一个字符
        # 因此，再定义一个后续释放键的操作，用于删除那个新增的字符

    def release_key_action(self, event):
        """定义释放按键的操作，即：删除添加到文本最后的cmd_str"""
        press_key = event.char.upper()
        if press_key not in self.press_cmd:
            if self.content:  # 说明不是一开始就按错了键
                self.render_text(self.content, all_tagged_strings=self.all_tagged_strings)
            else:  # 如果是一开始就按错了，那就从历史队列中取值
                content, all_tagged_strs = self.fallback_action()
                self.render_text(content)
        else:
            if self.no_sel_text:  # 没有选择文本
                content, all_tagged_strs = self.fallback_action(delete_last=False)
                self.render_text(content, all_tagged_strings=self.all_tagged_strings)
            else:
                self.render_text(self.content, all_tagged_strings=self.all_tagged_strings)
                self.save_to_history(self.content, self.all_tagged_strings)

    def fallback_action(self, event=None, act_msg=None, delete_last=True,
                        undo=False):
        """回退上一步的操作

        :param event:
        :param act_msg:
        :param delete_last: 是否删除上一步操作
        :param undo: 是否为撤销操作，如果为撤销，则进行两次pop
        :return:
        """
        if event:
            logger.info(event.char)
        if act_msg:
            logger.info(f'{act_msg}')
        if undo:  # 能点击撤销操作按钮，则len(self.history)>2
            self.history.pop()
            content, all_tagged_strs = self.history[-1]
            logger.info(f'历史队列长度：{len(self.history)}')
            return content, all_tagged_strs
        if len(self.history) == 1:
            # 历史队列中只有一个元素，回退后需要将该元素重新填入队列
            # 即，保证历史队列中总有一个元素
            content, all_tagged_strs = self.history[-1]
            logger.info(f'历史队列长度：{len(self.history)}')
            return content, all_tagged_strs
        elif len(self.history) > 1:
            if not delete_last:
                content, all_tagged_strs = self.history[-1]
            else:
                content, all_tagged_strs = self.history.pop()
            logger.info(f'历史队列长度：{len(self.history)}')
            return content, all_tagged_strs
        else:
            logger.error('历史队列为空！')
            raise

    def undo(self):
        """撤销操作"""
        logger.info("撤销操作")
        content, all_tagged_strings = self.fallback_action(undo=True)
        self.render_text(content, all_tagged_strings=all_tagged_strings)
        self.update_undo_btn()

    def get_text(self):
        """获取Text控件中的所有文本"""
        text = self.text.get("1.0", "end-1c")
        return text

    def tag_text(self, command):
        """根据键入的命令，对文本进行标注"""
        logger.info('开始标注')
        try:
            sel_first = self.text.index(tk.SEL_FIRST)  # 选定文本的开始位置
            sel_last = self.text.index(tk.SEL_LAST)  # 选定文本的结束位置
            self.no_sel_text = False
        except tk.TclError:
            logger.warning('未选择文本，无法进行标注')
            self.msg_lbl.config(text="先选择文本，再进行标注")
            self.no_sel_text = True
            return None, None, None
        former_text = self.text.get('1.0', sel_first)  # 从开始到sel_first的文本
        latter_text = self.text.get(sel_first, "end-1c")  # 从sel_first到最后的文本
        selected_string = self.text.selection_get()  # 选中的文本
        latter_text2 = latter_text[len(selected_string):]
        tagged_str, sel_last = self.tag_and_replace(selected_string, selected_string, command,
                                                    sel_last)
        all_tagged_strs = self.update_all_tagged_strs(command, sel_first, sel_last)
        former_text += tagged_str
        if self.auto_tag:
            logger.info('自动标注后续相同文本')
            content = former_text + auto_tagging(tagged_str, latter_text2)
        else:
            content = former_text + latter_text2
        logger.info('标注完成')
        return content, sel_last, all_tagged_strs

    def update_all_tagged_strs(self, key, start_index, end_index):
        """更新all_tagged_strs"""
        logger.info('更新已标注索引')
        tagged_str_index = self.history[-1][1].copy()
        tagged_str_index[start_index + '-' + end_index] = key
        # 并把所有的位于此标记后面的、同段落的索引位置全部更新
        new_all_tagged_strs = {}
        label = self.press_cmd[key]
        line_no = start_index.split('.')[0]
        for k in tagged_str_index:
            if k == start_index + '-' + end_index:
                new_all_tagged_strs[k] = tagged_str_index[k]
                continue
            if k.startswith(line_no):  # 处于同一行的
                _s, _e = k.split('-')
                # 且位于刚刚标记的位置的后面
                if int(_s.split('.')[1]) > int(start_index.split('.')[1]):
                    s = line_no + '.' + str(int(_s.split('.')[1]) + len(label) + 5)
                    e = line_no + '.' + str(int(_e.split('.')[1]) + len(label) + 5)
                    new_all_tagged_strs[s + '-' + e] = tagged_str_index[k]
                else:
                    new_all_tagged_strs[k] = tagged_str_index[k]
            else:
                new_all_tagged_strs[k] = tagged_str_index[k]
        logger.info('更新完成')
        return new_all_tagged_strs

    def tag_and_replace(self, content, string, cmd_key, index):
        """将content中的string进行标记，并返回最新的content和索引

        :param content: 包含标注内容的字符串，也可以和string相等
        :param string: 标注内容的字符串
        :param cmd_key: 键入的命令
        :param index: string最后一个字符所在的位置
        :return:
        """
        if cmd_key in self.press_cmd:
            # 对文本进行标注
            new_string = "[@" + string + "#" + self.press_cmd[cmd_key] + "*]"
            # 更新索引，行索引不变，列索引加上对应的字符数
            new_index = index.split('.')[0] + "." + str(int(index.split('.')[1]) + len(self.press_cmd[cmd_key]) + 5)
        else:
            logger.warning(f'无效的快捷键{cmd_key}')
            return content, index
        if content == string:
            return new_string, new_index
        else:
            content = content.replace(string, new_string, 1)
            return content, new_index

    def save_to_history(self, content='', all_tagged_strings=None):
        """将当前的Text控件的内容存储历史"""
        if all_tagged_strings is None:
            all_tagged_strings = {}
        logger.info(f'写入历史队列')
        self.history.append([content, all_tagged_strings])
        logger.info(f'历史队列元素数量：{len(self.history)}')
        self.update_undo_btn()
        if len(self.history) > 1:
            self.format_btn.config(state='disabled')
        else:
            self.format_btn.config(state='normal')

    def update_undo_btn(self):
        """更新undo_btn控件的状态，目前控件一共包括：
        """
        if len(self.history) < 2:
            self.undo_btn.config(state='disabled')
        else:
            self.undo_btn.config(state='normal')

    def set_shortcuts_layout(self):
        """规划「快捷键」的布局"""
        if os.path.isfile(self.config_file):
            try:
                with open(self.config_file, 'r') as fp:
                    self.press_cmd = {k.upper(): v for k, v in json.load(fp).items()}
            except Exception:
                self.msg_lbl.config(text='错误！！配置文件非法，必须符合json格式')
                logger.critical('配置文件非法，必须符合json格式')
                logger.info('回退至上一个配置文件')
                self.config_file = self.former_cfg_file
                self.on_select()
                # raise InvalidShortcut("非法的配置文件格式")
        for k in self.press_cmd:
            if len(k) > 1:
                self.msg_lbl.config(text=f"错误！！`{k}:{self.press_cmd[k]}`错误，自定义的快捷键只能是一个字符")
                logger.critical(f"`{k}:{self.press_cmd[k]}`错误，自定义的快捷键只能是一个字符")
                logger.info('回退至上一个配置文件')
                self.config_file = self.former_cfg_file
                self.on_select()
                # raise InvalidShortcut(f"{k}错误，自定义的快捷键只能是一个字符")
        # 因为固定了行数，快捷键最多只能展示前10个
        if len(self.press_cmd) > 10:
            logger.warning("最多只能展示前10个快捷键")
        row = 5
        # 快捷键提示文本
        map_label = tk.Label(self, text="快捷键说明：",
                             foreground="#3399ff", font=(self.word_style, 14, "bold"))
        map_label.grid(row=row + 3, column=self.frame_cols + 1, columnspan=2, sticky='w', padx=10)

        # 销毁已有的控件(Entry和Label)
        if self.entry_list is not None:
            for x in self.entry_list:
                x.destroy()
        if self.label_list is not None:
            for x in self.label_list:
                x.destroy()
        self.entry_list = []
        self.label_list = []
        self.key_color_mapping = {}
        # 更新控件
        row = 9  # 从第10行开始（索引是9）
        count = 1
        for key in sorted(self.press_cmd):
            if count > 10:
                break
            color = color_mapping[count - 1]
            # todo
            # 给每一种快捷键添加上对应的背景色与前景色
            self.text.tag_config(f'ent-{key}', background=color['bg'], foreground=color['fg'])
            self.key_color_mapping[key] = count - 1
            label = tk.Label(self, text=key.upper() + ":", foreground="blue", anchor='e',
                             font=(self.word_style, 14, "bold"))
            label.grid(row=row, column=self.frame_cols + 1, columnspan=1, rowspan=1, padx=3)
            self.label_list.append(label)

            entry = tk.Entry(self, fg=color['fg'], bg=color['bg'], font=(self.word_style, 14, "bold"))
            entry.insert(0, self.press_cmd[key])
            entry.grid(row=row, column=self.frame_cols + 2, columnspan=1, rowspan=1)
            self.entry_list.append(entry)
            count += 1
            row += 1
        while count < 10:
            label = tk.Label(self, text="Undefined:", foreground="grey", anchor='e',
                             font=(self.word_style, 14, "bold"))
            label.grid(row=row, column=self.frame_cols + 1, columnspan=1, rowspan=1, padx=3)
            self.label_list.append(label)
            entry = tk.Entry(self, fg="black", bg='#a6a6a6', font=(self.word_style, 14,),
                             textvariable=tk.StringVar(value='暂未定义快捷键'))
            entry.grid(row=row, column=self.frame_cols + 2, columnspan=1, rowspan=1)
            self.entry_list.append(entry)
            count += 1
            row += 1
        self.set_combobox()

    def set_combobox(self):
        """设置下拉列表的动作"""
        row = 5
        if self.sc_lbl is not None:
            self.sc_lbl.destroy()
        if self.config_box is not None:
            self.config_box.destroy()
        lbl = tk.Label(self, text='快捷键', anchor='w', width=10, foreground="blue", font=(self.word_style, 20, "bold"))
        lbl.grid(row=row + 1, column=self.frame_cols + 1, sticky='w')

        self.sc_lbl = tk.Label(self, text="选择模板：", foreground="#3399ff",
                               font=(self.word_style, 14, "bold"), padx=10)
        self.sc_lbl.grid(row=row + 2, column=self.frame_cols + 1, sticky='w')
        # 下拉列表控件
        self.config_box = ttk.Combobox(self, values=get_cfg_files(), state='readonly')
        self.config_box.grid(row=row + 2, column=self.frame_cols + 2, sticky='w', padx=(0, 10))
        # 默认的配置文件设置
        self.config_box.set(self.config_file.split(os.sep)[-1])
        self.config_box.bind('<<ComboboxSelected>>', self.on_select)

    def on_select(self, event=None):
        """选择了配置文件后，更新布局"""
        if event:
            logger.info(f"从{event.widget.get()}获取快捷键设置")
            self.former_cfg_file = self.config_file
            self.config_file = os.path.join("configs", event.widget.get())
        else:
            logger.info(f'从{self.config_file}获取配置文件')
        self.set_shortcuts_layout()

    def export(self):
        # 按照换行符进行分割，此时仍有空白行，在按段落遍历时去除
        text_paras = open(self.file_name).readlines()
        new_filename = self.file_name.split('.ann')[0] + '.anns'
        f = open(new_filename, 'w')
        for i in range(len(text_paras)):
            p = text_paras[i]
            p = p.strip()
            if not p:
                continue
            else:
                tagged_words = get_tagged_pairs(p, self.schema, self.entity_re)
                for w in tagged_words:
                    f.write(w)
                if i != len(text_paras) - 1:
                    f.write('\n')
        f.close()
        self.msg_lbl.config(text='导出成功')

    def format(self):
        """格式化文本，去除多余的换行符"""
        content = self.get_text()
        text = '\n'.join([i for i in content.split('\n') if i])
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, text)
        # self.setColorDisplay()
        self.render_color()

    def render_color(self, all_tagged_strings=None):
        """渲染标注过的文本的颜色"""
        if all_tagged_strings is None:
            all_tagged_strings = {}
        for idx in all_tagged_strings:
            s, e = idx.split('-')
            key = all_tagged_strings[idx]
            self.text.tag_add(f'ent-{key}', s, e)

    def render_text(self, content, cr_psn=None, all_tagged_strings=None):
        """渲染Text控件，包括文本的重新加载和颜色的渲染"""
        if all_tagged_strings is None:
            all_tagged_strings = {}
        logger.info('重新加载文本')
        self.text.delete("1.0", tk.END)
        self.text.insert("end-1c", content)
        if cr_psn:
            self.text.mark_set(tk.INSERT, cr_psn)
            self.text.see(cr_psn)
            self.update_cr_psn(cr_psn)
        logger.info('渲染颜色')
        self.render_color(all_tagged_strings)


def get_cfg_files():
    """获取目标路径下所有的配置文件名"""
    file_names = os.listdir("./configs")
    return sorted([x for x in file_names if (not x.startswith('.')) and x.endswith('.config')])


def get_tagged_pairs(para, schema="BMES", rep=r'\[\@.*?\#.*?\*\]'):
    """对一个段落中的所有文本进行标注

    :param para: 段落文本
    :param schema: 标注方法
    :param rep: 匹配标注的文本的正则表达式
    :return:
    """
    para = para.strip('\n')
    ent_list = re.findall(rep, para)
    para_len = len(para)
    chunk_list = []  # 存储标注过的实体及相关信息
    end_pos = 0
    if not ent_list:
        chunk_list.append([para, 0, para_len, False])
    else:
        for pattern in ent_list:
            start_pos = end_pos + para[end_pos:].find(pattern)
            end_pos = start_pos + len(pattern)
            chunk_list.append([pattern, start_pos, end_pos, True])

    full_list = []  # 将整个para存储进来，并添加标识（是否为标注的实体）
    for idx in range(len(chunk_list)):
        if idx == 0:  # 对于第一个实体，要处理实体之前的文本
            if chunk_list[idx][1] > 0:  # 说明实体不是从该para的第一个字符开始的
                full_list.append([para[0:chunk_list[idx][1]], 0, chunk_list[idx][1], False])
                full_list.append(chunk_list[idx])
            else:
                full_list.append(chunk_list[idx])
        else:  # 对于后续的实体
            if chunk_list[idx][1] == chunk_list[idx - 1][2]:
                # 说明两个实体是相连的，直接将后一个实体添加进来
                full_list.append(chunk_list[idx])
            elif chunk_list[idx][1] < chunk_list[idx - 1][2]:
                # 不应该出现后面实体的开始位置比前面实体的结束位置还靠前的情况
                pass
            else:
                # 先将两个实体之间的文本添加进来
                full_list.append([para[chunk_list[idx - 1][2]:chunk_list[idx][1]],
                                  chunk_list[idx - 1][2], chunk_list[idx][1],
                                  False])
                # 再将下一个实体添加进来
                full_list.append(chunk_list[idx])

        if idx == len(chunk_list) - 1:  # 处理最后一个实体
            if chunk_list[idx][2] > para_len:
                # 最后一个实体的终止位置超过了段落长度，不应该出现这种情况
                pass
            elif chunk_list[idx][2] < para_len:
                # 将最后一个实体后面的文本添加进来
                full_list.append([para[chunk_list[idx][2]:para_len], chunk_list[idx][2], para_len, False])
            else:
                # 最后一个实体已经达到段落结尾，不作任何处理
                pass
    return tag_para(full_list, schema)


def tag_para(seg_list, schema="BMES"):
    """将段落中所有的字进行标注。

    :param seg_list: 由标注的实体词元素列表组成的列表
    :param schema: 标注方法
    :return:
    """
    pair_list = []
    for sub_list in seg_list:
        if sub_list[3]:  # 是标注的实体
            ent_and_lab = sub_list[0].strip('[@$*]').split('#')
            ent, label = ent_and_lab
            ent = list(ent)
            tagged_txt = tag_entity(ent, label, schema)
            for i in tagged_txt:
                pair_list.append(i)
        else:  # 不是实体
            txt = sub_list[0]
            txt = list(txt)
            for idx in range(len(txt)):
                word = txt[idx]
                if word == ' ':
                    continue
                pair = word + ' ' + 'O\n'
                pair_list.append(pair)
    return pair_list


def tag_entity(word_list, label: str, schema: str = "BMES"):
    """将实体字列表（word_list）中的每个字按照给定的模式（schema）打上
    对应的标签（label）

    :param word_list: 将实体词拆成单字组成的列表
    :param label: 实体对应的标签
    :param schema: 标注方法
    :return:
    """
    assert schema in ['BMES', 'BI'], f"不支持的标注模式{schema}"
    output_list = []
    list_len = len(word_list)
    if list_len == 1:
        if schema == 'BMES':
            return word_list[0] + ' ' + 'S_' + label + '\n'
        else:
            return word_list[0] + ' ' + 'B_' + label + '\n'
    else:
        if schema == 'BMES':
            for idx in range(list_len):
                if idx == 0:
                    pair = word_list[idx] + ' ' + 'B_' + label + '\n'
                elif idx == list_len - 1:
                    pair = word_list[idx] + ' ' + 'E_' + label + '\n'
                else:
                    pair = word_list[idx] + ' ' + 'M_' + label + '\n'
                output_list.append(pair)

        else:
            for idx in range(list_len):
                if idx == 0:
                    pair = word_list[idx] + ' ' + 'B_' + label + '\n'
                else:
                    pair = word_list[idx] + ' ' + 'I_' + label + '\n'
                output_list.append(pair)
        return output_list


def main():
    logger.info(f'当前操作系统：{platform.system()}')
    root = tk.Tk()
    root.geometry("1300x700+200+200")
    _ = MyFrame(root)
    logger.info('标注工具已经启动')
    root.mainloop()
    logger.info('标注工具已经关闭')


class InvalidShortcut(Exception):
    pass


if __name__ == '__main__':
    main()
