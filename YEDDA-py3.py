# -*- coding: utf-8 -*-
# macOS下：tkinter的Button控件兼容性有问题，无法设置控件格式
import sys
import tkinter as tk
import platform
from tkinter import font, messagebox, filedialog, ttk, Button
from collections import deque
import os.path
from utils import auto_tagging
import json
from typing import List
from utils.colors import color_mapping


class MyFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.title = "文本标注工具"
        self._os = platform.system().lower()
        self.parent = parent
        self.file_name = ""
        self.debug = False
        self.colorAllChunk = True
        self.auto_tag = False
        self.recommendFlag = False
        self.history = deque(maxlen=20)  # 存储操作历史，最多存储20步
        self.currentContent = deque(maxlen=1)
        # 初始的"按键-指令"映射关系
        self.press_cmd = {}
        self.all_keys = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        self.controlCommand = {'q': "unTag", 'ctrl+z': 'undo'}
        self.all_tagged_strs = {}  # 存储所有标注的文本的索引，及其对应的快捷键
        # 存储解释快捷键对应含义的Entry的List
        self.entry_list = []
        # 存储快捷键名称的Label的List
        self.label_list = []
        # ShortCuts Label
        self.sc_lbl = None
        # 显示配置文件名称的下拉列表控件
        self.config_box = None

        self.frame_rows = 20  # 固定行数
        self.frame_cols = 5  # 固定列数
        self.schema = "BMES"  # 默认的标注模式
        self.keepRecommend = True
        # 原作者想要的是通过此参数判断待标注的句子是否用空格来划分从而进行不同的操作，
        # 在我的代码里，不对此进行区分，因此，这个参数总是保持False。
        self.segmented = False
        self.config_file = "configs/default.config"
        self.entity_re = r'\[\@.*?\#.*?\*\](?!\#)'  # 标注后的词语的正则表达式
        # configure color
        self.entityColor = "green"
        self.insideNestEntityColor = "light slate blue"
        self.recommendColor = 'lightgreen'
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

        btn = Button(self, text="格式化", command=self.format, width=12)
        btn.grid(row=2, column=self.frame_cols + 2, pady=4)

        btn = Button(self, text="导出", command=self.export, width=12)
        btn.grid(row=3, column=self.frame_cols + 1, pady=4)

        btn = Button(self, text="退出程序", bg='red', command=self.quit, width=12)
        btn.grid(row=3, column=self.frame_cols + 2, pady=4)

        # todo: 增加更多的功能键
        #

        # 光标的当前位置(cursor position)
        self.cr_psn = tk.Label(self, text=("row: %s\ncol: %s" % (0, 0)),
                               font=(self.word_style, 10, "bold"))
        self.cr_psn.grid(row=self.frame_rows + 1, column=self.frame_cols + 2, pady=4)

        cmd_lbl = tk.Label(self, text="输入命令:", anchor='w')
        cmd_lbl.grid(row=self.frame_rows + 1, column=0, sticky=tk.E + tk.W + tk.S + tk.N, pady=4, padx=10)
        self.cmd_entry = tk.Entry(self)
        self.cmd_entry.grid(row=self.frame_rows + 1, column=0,
                            columnspan=self.frame_cols,
                            sticky=tk.E + tk.W + tk.S + tk.N, pady=4, padx=80)
        self.cmd_entry.bind('<Return>', self.returnEnter)

        # 在Text控件中按下不同的键，绑定对应的操作
        for press_key in self.all_keys:
            # 按下时，就进行标注
            self.text.bind(press_key, self.press_key_action)
            # 标注完成后，需要在释放所按键时删除输入的所按键的字符
            release = "<KeyRelease-" + press_key + ">"
            self.text.bind(release, self.delete_cmd_str)

            if self._os != "windows":
                controlPlusKey = "<Control-Key-" + press_key + ">"
                self.text.bind(controlPlusKey, self.keepCurrent)
                altPlusKey = "<Command-Key-" + press_key + ">"
                self.text.bind(altPlusKey, self.keepCurrent)

        self.text.bind('<Control-Key-z>', self.backToHistory)
        # disable the default  copy behaivour when right click.
        # For MacOS, right click is button 2, other systems are button3
        self.text.bind('<Button-2>', self.rightClick)
        self.text.bind('<Button-3>', self.rightClick)

        self.text.bind('<Double-Button-1>', self.doubleLeftClick)
        self.text.bind('<ButtonRelease-1>', self.singleLeftClick)

        self.set_shortcuts_layout()

        self.enter = Button(self, text="Enter", command=self.returnButton)
        self.enter.grid(row=self.frame_rows + 1, column=self.frame_cols + 1)

    # cursor index show with the left click
    def singleLeftClick(self, event):
        if self.debug:
            print(str(sys._getframe().f_lineno) + " Action Track: singleLeftClick")
        cursor_index = self.text.index(tk.INSERT)
        row_column = cursor_index.split('.')
        cursor_text = ("row: %s\ncol: %s" % (row_column[0], row_column[-1]))
        self.cr_psn.config(text=cursor_text)

    def doubleLeftClick(self, event):
        if self.debug:
            print(str(sys._getframe().f_lineno) + " Action Track: doubleLeftClick")
        pass

    # Disable right click default copy selection behaviour
    def rightClick(self, event):
        if self.debug:
            print(str(sys._getframe().f_lineno) + " Action Track: rightClick")
        try:
            firstSelection_index = self.text.index(tk.SEL_FIRST)
            cursor_index = self.text.index(tk.SEL_LAST)
            content = self.text.get('1.0', "end-1c").encode('utf-8')
            self.write_to_file(self.file_name, content, cursor_index)
        except tk.TclError:
            pass

    def setInRecommendModel(self):
        self.recommendFlag = True
        self.RecommendModelFlag.config(text=str(self.recommendFlag))
        messagebox.showinfo("Recommend Model", "Recommend Model has been activated!")

    def setInNotRecommendModel(self):
        self.recommendFlag = False
        self.RecommendModelFlag.config(text=str(self.recommendFlag))
        content = self.get_text()
        content = removeRecommendContent(content, self.recommendRe)
        self.write_to_file(self.file_name, content, '1.0')
        messagebox.showinfo("Recommend Model", "Recommend Model has been deactivated!")

    def open_file(self):
        ftps = [('all files', '.*'), ('text files', '.txt'), ('ann files', '.ann')]
        dlg = filedialog.Open(self, filetypes=ftps)
        fl = dlg.show()
        if fl != '':
            # 删除text控件中的内容
            self.text.delete("1.0", tk.END)
            # 读取内容并插入text控件
            text = self.read_file(fl)
            self.text.insert(tk.END, text)
            # 更新显示的文件路径
            self.set_label("文件位置：" + fl)
            self.autoLoadNewFile(self.file_name, "1.0")

            # self.text.mark_set(tk.INSERT, "1.0")
            # self.setCursorLabel(self.text.index(tk.INSERT))

    def read_file(self, file_name):
        f = open(file_name, "r")
        text = f.read()
        self.file_name = file_name
        return text

    def setFont(self, value):
        _family = self.word_style
        _size = value
        _weight = "bold"
        _underline = 0
        fnt = font.Font(family=_family, size=_size, weight=_weight, underline=_underline)
        tk.Text(self, font=fnt)

    def set_label(self, new_file):
        """更新Label控件的显示内容"""
        self.lbl.config(text=new_file)

    def setCursorLabel(self, cursor_index):
        if self.debug:
            print(str(sys._getframe().f_lineno) + " Action Track: setCursorLabel")
        row_column = cursor_index.split('.')
        cursor_text = ("row: %s\ncol: %s" % (row_column[0], row_column[-1]))
        self.cr_psn.config(text=cursor_text)

    def returnButton(self):
        if self.debug:
            print(str(sys._getframe().f_lineno) + " Action Track: returnButton")
        self.push_to_history()
        # self.returnEnter(event)
        content = self.cmd_entry.get()
        self.clearCommand()
        self.executeEntryCommand(content)
        return content

    def returnEnter(self, event):
        if self.debug:
            print(str(sys._getframe().f_lineno) + " Action Track: returnEnter")
        self.push_to_history()
        content = self.cmd_entry.get()
        self.clearCommand()
        self.executeEntryCommand(content)
        return content

    def press_key_action(self, event):
        """按下一个键位时，对应的操作"""
        # 获取按下的键对应的字符
        press_key = event.char
        if self.debug:
            print(str(sys._getframe().f_lineno) + f" Action Track: 捕获按键{press_key}")
        self.push_to_history()
        # self.clearCommand()
        self.tag_text(press_key.lower())
        return press_key

    def backToHistory(self, event):
        if self.debug:
            print(str(sys._getframe().f_lineno) + " Action Track: backToHistory")
        if len(self.history) > 0:
            historyCondition = self.history.pop()
            # print "history condition: ", historyCondition
            historyContent = historyCondition[0]
            # print "history content: ", historyContent
            cursorIndex = historyCondition[1]
            # print "get history cursor: ", cursorIndex
            self.write_to_file(self.file_name, historyContent, cursorIndex)
        else:
            print(str(sys._getframe().f_lineno) + " History is empty!")
        self.text.insert(tk.INSERT, 'p')  # add a word as pad for key release delete

    def keepCurrent(self, event):
        if self.debug:
            print(str(sys._getframe().f_lineno) + " Action Track: keepCurrent")
        print(str(sys._getframe().f_lineno) + " keep current, insert:%s" % tk.INSERT)
        print(str(sys._getframe().f_lineno) + " before:", self.text.index(tk.INSERT))
        self.text.insert(tk.INSERT, 'p')
        print(str(sys._getframe().f_lineno) + " after:", self.text.index(tk.INSERT))

    def clearCommand(self):
        if self.debug:
            print(str(sys._getframe().f_lineno) + " Action Track: clearCommand")
        self.cmd_entry.delete(0, 'end')

    def get_text(self):
        """获取Text控件中的所有文本"""
        text = self.text.get("1.0", "end-1c")
        return text

    def tag_text(self, command):
        """根据键入的命令，对文本进行标注"""
        if self.debug:
            print(str(sys._getframe().f_lineno) + " Action Track: executeCursorCommand")
            print(str(sys._getframe().f_lineno) + " 输入指令:" + command)
        try:
            sel_first = self.text.index(tk.SEL_FIRST)  # 选定文本的开始位置
            sel_last = self.text.index(tk.SEL_LAST)  # 选定文本的结束位置
            former_text = self.text.get('1.0', sel_first)  # 从开始到sel_first的文本
            latter_text = self.text.get(sel_first, "end-1c")  # 从sel_first到最后的文本
            selected_string = self.text.selection_get()  # 选中的文本
            print(selected_string)
            if re.match(self.entity_re, selected_string) != None:
                print("嵌套的")
                print(selected_string)
                new_string_list = selected_string.strip('[@]').rsplit('#', 1)
                new_string = new_string_list[0]
                latter_text = latter_text.replace(selected_string, new_string, 1)
                selected_string = new_string
                sel_last = sel_last.split('.')[0] + "." + str(
                    int(sel_last.split('.')[1]) - len(new_string_list[1]) + 4)
            latter_text2 = latter_text[len(selected_string):]

            if command == "q":
                print('q: remove entity label')
            else:
                if len(selected_string) > 0:
                    tagged_str, sel_last = self.tag_and_replace(selected_string, selected_string, command,
                                                                sel_last)
                    self.update_all_tagged_strs(command, sel_first, sel_last)
            former_text += tagged_str
            if self.auto_tag:
                content = former_text + auto_tagging(tagged_str, latter_text2)
            else:
                content = former_text + latter_text2
            # content = self.addRecommendContent(former_text, latter_text2, self.recommendFlag)
            self.write_to_file(self.file_name, content, sel_last)
        except tk.TclError:
            cursor_index = self.text.index(tk.INSERT)
            [line_id, column_id] = cursor_index.split('.')
            aboveLine_content = self.text.get('1.0', str(int(line_id) - 1) + '.end')
            belowLine_content = self.text.get(str(int(line_id) + 1) + '.0', "end-1c")
            line = self.text.get(line_id + '.0', line_id + '.end')
            matched_span = (-1, -1)
            detected_entity = -1
            for match in re.finditer(self.entity_re, line):
                if match.span()[0] <= int(column_id) & int(column_id) <= match.span()[1]:
                    matched_span = match.span()
                    detected_entity = 1
                    break
            if detected_entity == -1:
                for match in re.finditer(self.recommendRe, line):
                    if match.span()[0] <= int(column_id) & int(column_id) <= match.span()[1]:
                        matched_span = match.span()
                        detected_entity = 2
                        break
            line_before_entity = line
            line_after_entity = ""
            if matched_span[1] > 0:
                selected_string = line[matched_span[0]:matched_span[1]]
                if detected_entity == 1:
                    new_string_list = selected_string.strip('[@*]').rsplit('#', 1)
                elif detected_entity == 2:
                    new_string_list = selected_string.strip('[$*]').rsplit('#', 1)
                new_string = new_string_list[0]
                old_entity_type = new_string_list[1]
                line_before_entity = line[:matched_span[0]]
                line_after_entity = line[matched_span[1]:]
                selected_string = new_string
                tagged_str = selected_string
                cursor_index = line_id + '.' + str(int(matched_span[1]) - (len(new_string_list[1]) + 4))
                if command == "q":
                    print('q: remove entity label')
                elif command == 'y':
                    print(str(sys._getframe().f_lineno) + " y: comfirm recommend label")
                    old_key = self.press_cmd.keys()[self.press_cmd.values().index(old_entity_type)]
                    tagged_str, cursor_index = self.tag_and_replace(selected_string, selected_string, old_key,
                                                                    cursor_index)
                else:
                    if len(selected_string) > 0:
                        if command in self.press_cmd:
                            tagged_str, cursor_index = self.tag_and_replace(selected_string, selected_string,
                                                                            command,
                                                                            cursor_index)
                        else:
                            return
                line_before_entity += tagged_str
            if aboveLine_content != '':
                former_text = aboveLine_content + '\n' + line_before_entity
            else:
                former_text = line_before_entity

            if belowLine_content != '':
                latter_text = line_after_entity + '\n' + belowLine_content
            else:
                latter_text = line_after_entity

            content = self.addRecommendContent(former_text, latter_text, self.recommendFlag)
            # content = content.encode('utf-8')
            self.write_to_file(self.file_name, content, cursor_index)

    def executeEntryCommand(self, command):
        if self.debug:
            print(str(sys._getframe().f_lineno) + " Action Track: executeEntryCommand")
        if len(command) == 0:
            currentCursor = self.text.index(tk.INSERT)
            newCurrentCursor = str(int(currentCursor.split('.')[0]) + 1) + ".0"
            self.text.mark_set(tk.INSERT, newCurrentCursor)
            self.setCursorLabel(newCurrentCursor)
        else:
            command_list = decompositCommand(command)
            for idx in range(0, len(command_list)):
                command = command_list[idx]
                if len(command) == 2:
                    select_num = int(command[0])
                    command = command[1]
                    content = self.get_text()
                    cursor_index = self.text.index(tk.INSERT)
                    newcursor_index = cursor_index.split('.')[0] + "." + str(
                        int(cursor_index.split('.')[1]) + select_num)
                    # print "new cursor position: ", select_num, " with ", newcursor_index, "with ", newcursor_index
                    selected_string = self.text.get(cursor_index, newcursor_index).encode('utf-8')
                    aboveHalf_content = self.text.get('1.0', cursor_index).encode('utf-8')
                    followHalf_content = self.text.get(cursor_index, "end-1c").encode('utf-8')
                    if command in self.press_cmd:
                        if len(selected_string) > 0:
                            # print "insert index: ", self.text.index(INSERT) 
                            followHalf_content, newcursor_index = self.tag_and_replace(followHalf_content,
                                                                                       selected_string, command,
                                                                                       newcursor_index)
                            content = self.addRecommendContent(aboveHalf_content, followHalf_content,
                                                               self.recommendFlag)
                            # content = aboveHalf_content + followHalf_content
                    self.write_to_file(self.file_name, content, newcursor_index)

    def update_all_tagged_strs(self, key, start_index, end_index):
        """更新all_tagged_strs"""
        self.all_tagged_strs[start_index + '-' + end_index] = key
        # 并把所有的位于此标记后面的、同段落的索引位置全部更新
        new_all_tagged_strs = {}
        label = self.press_cmd[key]
        line_no = start_index.split('.')[0]
        for k in self.all_tagged_strs:
            if k == start_index + '-' + end_index:
                new_all_tagged_strs[k] = self.all_tagged_strs[k]
                continue
            if k.startswith(line_no):  # 处于同一行的
                _s, _e = k.split('-')
                # 且位于刚刚标记的位置的后面
                if int(_s.split('.')[1]) > int(start_index.split('.')[1]):
                    s = line_no + '.' + str(int(_s.split('.')[1]) + len(label) + 5)
                    e = line_no + '.' + str(int(_e.split('.')[1]) + len(label) + 5)
                    new_all_tagged_strs[s + '-' + e] = self.all_tagged_strs[k]
                else:
                    new_all_tagged_strs[k] = self.all_tagged_strs[k]
            else:
                new_all_tagged_strs[k] = self.all_tagged_strs[k]
        self.all_tagged_strs = new_all_tagged_strs

    def delete_cmd_str(self, event):
        """删除command的str，限定每个命令只占一个字符"""
        index = self.text.index(tk.INSERT)
        if self.debug:
            print(str(sys._getframe().f_lineno) + " Action Track: delete_cmd_str")
            print(str(sys._getframe().f_lineno) + " delete insert:", index)
        indexes = index.split('.')
        former_index = indexes[0] + "." + str(int(indexes[1]) - 1)
        cmd_str = self.text.get(former_index, index)
        former_txt = self.text.get('1.0', former_index)
        latter_txt = self.text.get(former_index, "end-1c")[1:]  # 去除了cmd_str
        content = former_txt + latter_txt
        self.write_to_file(self.file_name, content, former_index)

    def tag_and_replace(self, content: str, string: str, cmd_key: str, index: str):
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
            new_index = index.split('.')[0] + "." + \
                        str(int(index.split('.')[1]) + len(self.press_cmd[cmd_key]) + 5)
        else:
            print(str(sys._getframe().f_lineno) + " Invaild command!")
            print(str(sys._getframe().f_lineno) + " cursor index: ", self.text.index(tk.INSERT))
            return content, index
        if content == string:
            return new_string, new_index
        else:
            content = content.replace(string, new_string, 1)
            return content, new_index

    def write_to_file(self, file_name, content, newcursor_index):
        if self.debug:
            print(str(sys._getframe().f_lineno) + " Action track: writeFile")

        if len(file_name) > 0:
            if ".ann" in file_name:
                new_name = file_name
                ann_file = open(new_name, 'w')
                ann_file.write(content)
                ann_file.close()
            else:
                new_name = file_name + '.ann'
                ann_file = open(new_name, 'w')
                ann_file.write(content)
                ann_file.close()
            self.autoLoadNewFile(new_name, newcursor_index)
        else:
            print(str(sys._getframe().f_lineno) + " Don't write to empty file!")

    def addRecommendContent(self, tagged_str: str, other_str: str, recommend_mode: bool) -> str:
        """根据已经标注的文本自动标注新的文本

        :param tagged_str: 已经标注的文本
        :param other_str: 未标注的文本
        :param recommend_mode: 是否启用自动标注模式
        :return:
        """
        if recommend_mode:
            if self.debug:
                print(str(sys._getframe().f_lineno) + " Action Track: addRecommendContent, start Recommend entity")
            content = maximum_matching(tagged_str, other_str)
        else:
            content = tagged_str + other_str
        return content

    def autoLoadNewFile(self, fileName, newcursor_index):
        if self.debug:
            print(str(sys._getframe().f_lineno) + " Action Track: autoLoadNewFile")
        if len(fileName) > 0:
            self.text.delete("1.0", tk.END)
            text = self.read_file(fileName)
            self.text.insert("end-1c", text)
            self.set_label("文件位置：" + fileName)
            self.text.mark_set(tk.INSERT, newcursor_index)
            self.text.see(newcursor_index)
            self.setCursorLabel(newcursor_index)
            # self.setColorDisplay()
            self.render_color()

    def setColorDisplay(self):
        if self.debug:
            print(str(sys._getframe().f_lineno) + " Action Track: setColorDisplay")
        self.text.config(insertbackground='red', insertwidth=4, font=self.fnt)

        countVar = tk.StringVar()
        currentCursor = self.text.index(tk.INSERT)
        lineStart = currentCursor.split('.')[0] + '.0'
        lineEnd = currentCursor.split('.')[0] + '.end'

        if self.colorAllChunk:
            self.text.mark_set("matchStart", "1.0")
            self.text.mark_set("matchEnd", "1.0")
            self.text.mark_set("searchLimit", 'end-1c')
            self.text.mark_set("recommend_matchStart", "1.0")
            self.text.mark_set("recommend_matchEnd", "1.0")
            self.text.mark_set("recommend_searchLimit", 'end-1c')
        else:
            self.text.mark_set("matchStart", lineStart)
            self.text.mark_set("matchEnd", lineStart)
            self.text.mark_set("searchLimit", lineEnd)
            self.text.mark_set("recommend_matchStart", lineStart)
            self.text.mark_set("recommend_matchEnd", lineStart)
            self.text.mark_set("recommend_searchLimit", lineEnd)
        while True:
            self.text.tag_configure("catagory", background=self.entityColor)
            self.text.tag_configure("edge", background=self.entityColor)
            pos = self.text.search(self.entity_re, "matchEnd", "searchLimit", count=countVar, regexp=True)
            if pos == "":
                break
            self.text.mark_set("matchStart", pos)
            self.text.mark_set("matchEnd", "%s+%sc" % (pos, countVar.get()))

            first_pos = pos
            second_pos = "%s+%sc" % (pos, str(1))
            lastsecond_pos = "%s+%sc" % (pos, str(int(countVar.get()) - 1))
            last_pos = "%s+%sc" % (pos, countVar.get())

            self.text.tag_add("catagory", first_pos, last_pos)
            # self.text.tag_add("catagory", second_pos, lastsecond_pos)
            # self.text.tag_add("edge", first_pos, second_pos)
            # self.text.tag_add("edge", lastsecond_pos, last_pos)
        ## color recommend type
        while True:
            self.text.tag_configure("recommend", background=self.recommendColor)
            recommend_pos = self.text.search(self.recommendRe, "recommend_matchEnd", "recommend_searchLimit",
                                             count=countVar, regexp=True)
            if recommend_pos == "":
                break
            self.text.mark_set("recommend_matchStart", recommend_pos)
            self.text.mark_set("recommend_matchEnd", "%s+%sc" % (recommend_pos, countVar.get()))

            first_pos = recommend_pos
            # second_pos = "%s+%sc" % (recommend_pos, str(1))
            lastsecond_pos = "%s+%sc" % (recommend_pos, str(int(countVar.get())))
            self.text.tag_add("recommend", first_pos, lastsecond_pos)

        ## color the most inside span for nested span, scan from begin to end again
        # if self.colorAllChunk:
        #     self.text.mark_set("matchStart", "1.0")
        #     self.text.mark_set("matchEnd", "1.0")
        #     self.text.mark_set("searchLimit", 'end-1c')
        # else:
        #     self.text.mark_set("matchStart", lineStart)
        #     self.text.mark_set("matchEnd", lineStart)
        #     self.text.mark_set("searchLimit", lineEnd)
        # while True:
        #     self.text.tag_configure("insideEntityColor", background=self.insideNestEntityColor)
        #     pos = self.text.search(self.insideNestEntityRe, "matchEnd", "searchLimit", count=countVar, regexp=True)
        #     if pos == "":
        #         break
        #     self.text.mark_set("matchStart", pos)
        #     self.text.mark_set("matchEnd", "%s+%sc" % (pos, countVar.get()))
        #     first_pos = "%s + %sc" % (pos, 2)
        #     last_pos = "%s + %sc" % (pos, str(int(countVar.get()) - 1))
        #     self.text.tag_add("insideEntityColor", first_pos, last_pos)

    def push_to_history(self):
        """存入历史"""
        if self.debug:
            print(str(sys._getframe().f_lineno) + " Action Track: pushToHistory")
        content = self.get_text()
        cr_psn = self.text.index(tk.INSERT)
        current = [content, cr_psn]  # 存储当前的操作，需要存储当前控件的内容以及光标的位置
        self.history.append(current)

    def pushToHistoryEvent(self, event):
        if self.debug:
            print(str(sys._getframe().f_lineno) + " Action Track: pushToHistoryEvent")
        currentList = []
        content = self.get_text()
        cursorPosition = self.text.index(tk.INSERT)
        # print "push to history cursor: ", cursorPosition
        currentList.append(content)
        currentList.append(cursorPosition)
        self.history.append(currentList)

    def renewPressCommand(self):
        if self.debug:
            print(str(sys._getframe().f_lineno) + " Action Track: renewPressCommand")
        seq = 0
        new_dict = {}
        list_length = len(self.entry_list)
        delete_num = 0
        for key in sorted(self.press_cmd):
            label = self.entry_list[seq].get()
            if len(label) > 0:
                new_dict[key] = label
            else:
                delete_num += 1
            seq += 1
        self.press_cmd = new_dict
        for idx in range(1, delete_num + 1):
            self.entry_list[list_length - idx].delete(0, tk.END)
            self.label_list[list_length - idx].config(text="NON= ")
        with open(self.config_file, 'wb') as fp:
            json.dump(self.press_cmd, fp)
        self.set_shortcuts_layout()
        messagebox.showinfo("Remap Notification",
                            "Shortcut map has been updated!\n\nConfigure file has been saved in File:" + self.config_file)

    def savenewPressCommand(self):
        if self.debug:
            print(str(sys._getframe().f_lineno) + " Action Track: savenewPressCommand")
        seq = 0
        new_dict = {}
        listLength = len(self.entry_list)
        delete_num = 0
        for key in sorted(self.press_cmd):
            label = self.entry_list[seq].get()
            if len(label) > 0:
                new_dict[key] = label
            else:
                delete_num += 1
            seq += 1
        self.press_cmd = new_dict
        for idx in range(1, delete_num + 1):
            self.entry_list[listLength - idx].delete(0, tk.END)
            self.label_list[listLength - idx].config(text="NON= ")
        # prompt to ask configFile name
        self.config_file = filedialog.asksaveasfilename(initialdir="./configs/",
                                                        title="Save New Config",
                                                        filetypes=(
                                                            ("YEDDA configs", "*.config"), ("all files", "*.*")))
        # change to relative path following self.init()
        self.config_file = os.path.relpath(self.config_file)
        # make sure ending with ".config"
        if not self.config_file.endswith(".config"):
            self.config_file += ".config"
        with open(self.config_file, 'wb') as fp:
            json.dump(self.press_cmd, fp)
        self.set_shortcuts_layout()
        messagebox.showinfo("Save New Map Notification",
                            "Shortcut map has been saved and updated!\n\nConfigure file has been saved in File:" + self.config_file)

    def set_shortcuts_layout(self):
        """规划「快捷键」的布局"""
        if os.path.isfile(self.config_file):
            with open(self.config_file, 'r') as fp:
                self.press_cmd = json.load(fp)
        for k in self.press_cmd:
            if len(k) > 1:
                messagebox.showerror('Error!', f"`{k}:{self.press_cmd[k]}`错误，自定义的快捷键只能是一个字符")
                raise InvalidShortcut(f"{k}错误，自定义的快捷键只能是一个字符")
        # 因为固定了行数，快捷键最多只能展示前10个
        if len(self.press_cmd) > 10 and self.debug:
            print(str(sys._getframe().f_lineno) + " 最多只能展示前10个快捷键")
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
            color = color_mapping[count-1]
            # todo
            # 给每一种快捷键添加上对应的背景色与前景色
            self.text.tag_config(f'ent-{key}', background=color['bg'], foreground=color['fg'])
            # self.text.tag_config(f'ent-{key}', bg='red', fg='black')
            self.key_color_mapping[key] = count - 1
            label = tk.Label(self, text=key.upper() + ":", foreground="blue", anchor='e',
                             font=(self.word_style, 14, "bold"))
            label.grid(row=row, column=self.frame_cols + 1, columnspan=1, rowspan=1, padx=3)
            self.label_list.append(label)

            entry = tk.Entry(self, foreground="blue", font=(self.word_style, 14, "bold"))
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

    def on_select(self, event=None):
        """选择了配置文件后，更新布局"""
        if event and self.debug:
            print(str(sys._getframe().f_lineno) + " 从", event.widget.get(), "获取快捷键设置")
        self.config_file = os.path.join("configs", event.widget.get())
        self.set_shortcuts_layout()

    def getCursorIndex(self):
        return self.text.index(tk.INSERT)

    def export(self):
        if (".ann" not in self.file_name) and (".txt" not in self.file_name):
            out_error = "Export only works on filename ended in .ann or .txt!\nPlease rename file."
            # todo
            print(out_error)
            messagebox.showerror("Export error!", out_error)
            return -1
        # 按照换行符进行分割，此时仍有空白行，在按段落遍历时去除
        text_paras = open(self.file_name, 'r').readlines()
        print(text_paras)
        num_paras = len(text_paras) + 1
        new_filename = self.file_name.split('.ann')[0] + '.anns'
        f = open(new_filename, 'w')
        for p in text_paras:
            if len(p) <= 2:  # 即line=='\n'
                f.write('\n')
                continue
            else:
                if not self.keepRecommend:
                    p = removeRecommendContent(p, self.recommendRe)
                tagged_words = get_tagged_pairs(p, self.segmented, self.schema, self.goldAndrecomRe)
                for w in tagged_words:
                    f.write(w)
                f.write('\n')
        f.close()
        print(str(sys._getframe().f_lineno) + " Exported file into sequence style in file: ", new_filename)
        print(str(sys._getframe().f_lineno) + " Line number:", num_paras)
        msg = f'''导出成功
标注方式：{self.schema}
句子总数：{num_paras}
保存地址：{new_filename}    
        '''
        messagebox.showinfo("Export Message", msg)

    def format(self):
        """格式化文本，去除多余的换行符"""
        content = self.get_text()
        text = '\n'.join([i for i in content.split('\n') if i])
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, text)
        # self.setColorDisplay()
        self.render_color()

    def render_color(self):
        """渲染标注过的文本的颜色"""
        print(self.all_tagged_strs)
        for idx in self.all_tagged_strs:
            s, e = idx.split('-')
            key = self.all_tagged_strs[idx]
            self.text.tag_add(f'ent-{key}',s, e)


def get_cfg_files():
    """获取目标路径下所有的配置文件名"""
    file_names = os.listdir("./configs")
    return sorted([x for x in file_names if (not x.startswith('.')) and x.endswith('.config')])


def get_tagged_pairs(para: str, segmented: bool = False, schema: str = "BMES",
                     rep: str = r'\[\@.*?\#.*?\*\]') -> List[str]:
    """对一个段落中的所有文本进行标注

    :param para: 段落文本
    :param segmented: 在本程序中始终为False
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
                # todo
                print(str(sys._getframe().f_lineno) + " ERROR: found pattern has overlap!", chunk_list[idx][1],
                      ' with ',
                      chunk_list[idx - 1][2])
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
                print(str(sys._getframe().f_lineno) + " ERROR: found pattern position larger than sentence length!")
            elif chunk_list[idx][2] < para_len:
                # 将最后一个实体后面的文本添加进来
                full_list.append([para[chunk_list[idx][2]:para_len], chunk_list[idx][2], para_len, False])
            else:
                # 最后一个实体已经达到段落结尾，不作任何处理
                pass
    return tag_para(full_list, segmented, schema)


def tag_para(seg_list: List[List], segmented=False, schema="BMES") -> List[str]:
    """将段落中所有的字进行标注。

    :param seg_list: 由标注的实体词元素列表组成的列表
    :param segmented: 在本程序中始终为False
    :param schema: 标注方法
    :return:
    """
    pair_list = []
    for sub_list in seg_list:
        if sub_list[3]:  # 是标注的实体
            ent_and_lab = sub_list[0].strip('[@$*]').split('#')
            if len(ent_and_lab) != 2:
                # todo
                print(str(sys._getframe().f_lineno) + " Error: sentence format error!")
            ent, label = ent_and_lab
            ent = list(ent) if not segmented else ent
            tagged_txt = tag_entity(ent, label, schema)
            for i in tagged_txt:
                pair_list.append(i)
        else:  # 不是实体
            txt = sub_list[0]
            txt = list(txt) if not segmented else txt
            for idx in range(len(txt)):
                word = txt[idx]
                if word == ' ':
                    continue
                pair = word + ' ' + 'O\n'
                pair_list.append(pair)
    return pair_list


def tag_entity(word_list: List[str], label: str, schema: str = "BMES") -> List[str]:
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


def removeRecommendContent(content, recommendRe=r'\[\$.*?\#.*?\*\](?!\#)'):
    output_content = ""
    last_match_end = 0
    for match in re.finditer(recommendRe, content):
        matched = content[match.span()[0]:match.span()[1]]
        words = matched.strip('[$]').split("#")[0]
        output_content += content[last_match_end:match.span()[0]] + words
        last_match_end = match.span()[1]
    output_content += content[last_match_end:]
    return output_content


def decompositCommand(command_string):
    command_list = []
    each_command = []
    num_select = ''
    for idx in range(0, len(command_string)):
        if command_string[idx].isdigit():
            num_select += command_string[idx]
        else:
            each_command.append(num_select)
            each_command.append(command_string[idx])
            command_list.append(each_command)
            each_command = []
            num_select = ''
    # print command_list
    return command_list


def main():
    print(str(sys._getframe().f_lineno) + " SUTDAnnotator launched!")
    print(str(sys._getframe().f_lineno) + " OS:%s" % (platform.system()))
    root = tk.Tk()
    root.geometry("1300x700+200+200")
    app = MyFrame(root)
    app.setFont(17)
    root.mainloop()


class InvalidShortcut(Exception):
    pass


if __name__ == '__main__':
    main()
