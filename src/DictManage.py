from .utils import *
import os
import shelve
import threading
import copy
from PyQt5.QtCore import QObject, QThread, Qt, QMetaObject
from PyQt5.QtGui import QColor


class Observer(QObject):
    def __init__(self):
        super().__init__()
        self.observer_thread = QThread.currentThread()

    def observer_update(self):
        pass

    def thread_safe_update(self):
        if QThread.currentThread() == self.observer_thread:
            self.observer_update()
        else:
            QMetaObject.invokeMethod(self, 'observer_update', Qt.QueuedConnection)


class DictManage():
    '''
    relation_graph结构
    {
        'category': {
            '质量': {
                'tag': {'高质量', '中质量', '低质量'},
                'tagOrder': ['高质量', '中质量', '低质量']
                'tagColor': '#79AD6B'
            },
        'tag': {
            'CG': {
                'category': {'一般'},  
                'file': {'file_path1', 'file_path2', ...}
            },  
            '高质量': {  
                'category': {'质量'},
                'file': {'file_path1', 'file_path2', ...} 
            }  
        },  
        'file': {  
            'file_path1': {  
                'tag': {'高质量', '日出', ...},
                'info': "str"
            },
            'file_path2': {  
                'tag': {'户外', '猫', ...},
                'info': "str"
            }
        }
    }
    '''
    # 单例
    _instance = None
    _initialized = False
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._initialized = True
            self.relation_graph = {}
            self.special_tags_status = {}
            self._lock = threading.Lock()
            self.load_tagbase()
            self._observers = []

    # 观察者模式
    def add_observer(self, observer):
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer):
        if observer in self._observers:
            self._observers.remove(observer)

    def notify_observers(self):
        for observer in self._observers:
            observer.thread_safe_update()

    def load_tagbase(self):
        floder_path = config.get('DictManage', 'tagbase_path', fallback='default_folder')
        if floder_path == 'default_folder':
            floder_path = os.path.join(root, 'data', 'tag')
        os.makedirs(floder_path, exist_ok=True)
        tagbase_name = config.get('DictManage', 'tagbase_name', fallback='tagbase')
        self.tag_dict_path = os.path.join(floder_path, tagbase_name)

        if not os.path.exists(self.tag_dict_path+".dir"):
            with shelve.open(self.tag_dict_path) as shelf:
                shelf['category_dict'] = {"未分类":{"tagColor":QColor(200, 200, 200).name(), "tags": set(), "tagOrder": []}}
                shelf['tag_dict'] = {}
                shelf['file_dict'] = {}
                shelf['special_tags_status'] = {}
        with shelve.open(self.tag_dict_path) as shelf:
            if shelf.get('category_dict') is None:
                shelf['category_dict'] = {"未分类":{"tagColor":QColor(200, 200, 200).name(), "tags": set(), "tagOrder": []}}
            if shelf.get('tag_dict') is None:
                shelf['tag_dict'] = {}
            if shelf.get('file_dict') is None:
                shelf['file_dict'] = {}
            if shelf.get('special_tags_status') is None:
                shelf['special_tags_status'] = {}
            self.relation_graph['category'] = shelf['category_dict']
            self.relation_graph['tag'] = shelf['tag_dict']
            self.relation_graph['file'] = shelf['file_dict']
            self.special_tags_status.update(shelf['special_tags_status'])

    # ——————————————————————————————————————————————————字典基础操作————————————————————————————————————————————————————

    def add_relation(self, source_group, source_entity, target_group, target_entity, double_mode=True):
        """  
        添加一个关系：source_group:source_entity -> target_group:target_entity  
        """  
        # 初始化起始方和实体
        if source_group not in self.relation_graph:  
            self.relation_graph[source_group] = {}
        if source_entity not in self.relation_graph[source_group]:  
            self.relation_graph[source_group][source_entity] = {}
        if target_group not in self.relation_graph[source_group][source_entity]:  
            self.relation_graph[source_group][source_entity][target_group] = set()
        # 添加目标实体 
        self.relation_graph[source_group][source_entity][target_group].add(target_entity)

        # 反向添加（默认）
        if double_mode:
            if target_group not in self.relation_graph:
                self.relation_graph[target_group] = {}  
            if target_entity not in self.relation_graph[target_group]:  
                self.relation_graph[target_group][target_entity] = {}  
            if source_group not in self.relation_graph[target_group][target_entity]:  
                self.relation_graph[target_group][target_entity][source_group] = set()  
            self.relation_graph[target_group][target_entity][source_group].add(source_entity)

    def remove_relation(self, source_group, source_entity, target_group, target_entity, double_mode=True):
        """
        删除一个关系：source_group:source_entity -> target_group:target_entity
        """
        try:
            self.relation_graph[source_group][source_entity][target_group].discard(target_entity)
        except:
            pass
        if double_mode:
            try:
                self.relation_graph[target_group][target_entity][source_group].discard(source_entity)
            except:
                pass

    def delete_entity(self, group, entity):
        """
        删除一个实体：group:entity 以及相关关系
        """
        if group not in self.relation_graph or entity not in self.relation_graph[group]:
            return False
        
        for target_group, targets in self.relation_graph[group][entity].items():
            if target_group in self.relation_graph:
                for target_entity in targets.copy():
                    self.remove_relation(group, entity, target_group, target_entity)

        del self.relation_graph[group][entity]
        return True
    
    def rename_entity(self, group, old_entity, new_entity, conflict_handler=None):
        """
        重命名一个实体：group:old_entity -> group:new_entity，保持字典顺序
        
        Args:
            group (str): 实体所属的组（'category', 'tag', 或 'file'）
            old_entity (str): 旧的实体名
            new_entity (str): 新的实体名
        """
        if group not in self.relation_graph or old_entity not in self.relation_graph[group]:
            return "key error"

        if new_entity in self.relation_graph[group] and not conflict_handler:
            return "name duplicate"

        # 添加新实体
        for target_group, targets in self.relation_graph[group][old_entity].items():
            if target_group in self.relation_graph:
                for target_entity in targets:
                    self.add_relation(target_group, target_entity, group, new_entity, double_mode=False)
        if new_entity in self.relation_graph[group]:
            conflict_handler(group, old_entity, new_entity)
        else:
            self.relation_graph[group][new_entity] = copy.deepcopy(self.relation_graph[group][old_entity])
        # 删除旧实体
        self.delete_entity(group, old_entity)
        return "success"
    
    def align(self):  
        """  
        对齐函数，自动添加缺失的实体。  
        """  
        # 遍历所有方  
        for group, entities in self.relation_graph.items():
            # 遍历方中的所有实体  
            for entity, relations in entities.items():
                # 遍历实体的所有目标方
                for target_group, targets in relations.items():
                    # 如果是双向关系，进行对齐
                    if target_group in self.relation_graph:
                    # 遍历目标实体  
                        for target_entity in targets:
                            # 如果目标实体不存在，初始化
                            if target_entity not in self.relation_graph[target_group]:
                                self.relation_graph[target_group][target_entity] = {}
                            # 添加反向关系
                            if group not in self.relation_graph[target_group][target_entity]:
                                self.relation_graph[target_group][target_entity][group] = set()  
                            if entity not in self.relation_graph[target_group][target_entity][group]:  
                                self.relation_graph[target_group][target_entity][entity].add(entity)

    def save_dict(self):
        with self._lock:
            with shelve.open(self.tag_dict_path) as shelf:
                shelf['category_dict'] = self.relation_graph['category']
                shelf['tag_dict'] = self.relation_graph['tag']
                shelf['file_dict'] = self.relation_graph['file']

    # ——————————————————————————————————————————业务基础操作————————————————————————————————————————

    # 添加tag
    def add_tag(self, tag:str, file_paths:list):
        # 检查tag是否存在
        if tag not in self.relation_graph['tag']:
            self.add_relation('tag', tag, 'category', '未分类')
            self.relation_graph['category']['未分类']['tagOrder'].append(tag)
        # 检查文件是否存在
        for file_path in file_paths[:]:
            if type(file_path) != str or not os.path.exists(file_path):
                file_paths.remove(file_path)
        # 更新 relation_graph
        for file_path in file_paths:
            self.add_relation('tag', tag, 'file', file_path)
        # 保存并通知
        self.save_notify()
    
    # 删除tag
    def delete_tag(self, tag, file_paths):
        for file_path in file_paths:
            self.remove_relation('tag', tag, 'file', file_path)
            # 如果文件没有关联的标签，则删除该文件条目
            if file_path in self.relation_graph['file'] and not self.relation_graph['file'][file_path].get('tag', False) and not self.relation_graph['file'][file_path].get('info', False):
                del self.relation_graph['file'][file_path]
        self.save_notify()

    # 删除tag实体及相关关系
    def destroy_tag(self, tag):
        file_paths = self.relation_graph['tag'].get(tag, {}).get('file', set())
        category = list(self.relation_graph['tag'][tag]['category'])[0]
        self.delete_entity("tag", tag)
        self.relation_graph['category'][category]['tagOrder'].remove(tag)
        for file_path in file_paths:
            if file_path in self.relation_graph['file'] and not self.relation_graph['file'][file_path].get('tag', False) and not self.relation_graph['file'][file_path].get('info', False):
                del self.relation_graph['file'][file_path]
        self.save_notify()

    def rename_tag(self, tag, new_name):
        def tag_duplicate_handler(_, old_name, new_name):
            self.relation_graph['tag'][new_name]['file'] |= self.relation_graph['tag'][old_name]['file']
        old_category = list(self.relation_graph['tag'][tag]['category'])[0]
        self.rename_entity('tag', tag, new_name, tag_duplicate_handler)
        new_category = list(self.relation_graph['tag'][new_name]['category'])[0]
        if old_category == new_category:
            index = self.relation_graph['category'][old_category]['tagOrder'].index(tag)
            self.relation_graph['category'][old_category]['tagOrder'][index] = new_name
        else:
            self.relation_graph['category'][old_category]['tagOrder'].remove(tag)
        self.save_notify()

    def change_tag_category(self, tag, category):
        old_category = list(self.relation_graph['tag'][tag]['category'])[0]
        if old_category == category:
            return "tag already in category"
        if category not in self.relation_graph['category']:
            self.relation_graph['category'][category] = {"tagColor":QColor(200, 200, 200).name(), "tags":set()}
        self.remove_relation('tag', tag, 'category', old_category)
        self.relation_graph['category'][old_category]['tagOrder'].remove(tag)
        self.add_relation('tag', tag, 'category', category)
        self.relation_graph['category'][category]['tagOrder'].append(tag)
        self.save_notify()
        return "success"

    def change_special_tags_status(self, tag, status):
        self.special_tags_status[tag] = status
        with shelve.open(self.tag_dict_path, writeback=True) as shelf:
            shelf['special_tags_status'] = self.special_tags_status

    def save_notify(self):
        # 保存更新后的字典
        self.save_dict()
        # 通知观察者更新
        self.notify_observers()

    def _change_sort(self, change_object, change_value, action):
        items = list(change_object)
        index = items.index(change_value)
        if action == 'up':
            if index > 0:
                items[index], items[index-1] = items[index-1], items[index]
        elif action == 'down':
            if index < len(items) - 1:
                items[index], items[index+1] = items[index+1], items[index]
        else:
            raise ValueError("action 必须是 'up' 或 'down'")
        return items

    def move_key(self, dictionary, key, action):
        key_list = self._change_sort(dictionary, key, action)
        new_dict = {}
        for key in key_list:
            new_dict[key] = dictionary[key]
        dictionary.clear()
        dictionary.update(new_dict)
        with shelve.open(self.tag_dict_path, writeback=True) as shelf:
            shelf['category_dict'] = self.relation_graph['category']
        self.notify_observers()

    def move_element(self, list_object, element, action):
        list_object[:] = self._change_sort(list_object, element, action)
        with shelve.open(self.tag_dict_path, writeback=True) as shelf:
            shelf['category_dict'] = self.relation_graph['category']
        self.notify_observers()

if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtGui import QColor
    import sys
    app = QApplication(sys.argv)
    dictmange = DictManage()
    # move_key单测
    dictionary = {'a': 1, 'b': [1,'2',5], 'c': 'dwa', 'd': 4}
    print(dictmange.move_key(dictionary, 'b', 'down'))  # 输出: {'a': 1, 'b': 2, 'c': 3, 'd': 4}