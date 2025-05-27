import shelve
path = r"C:\Users\zhang\Desktop\Tag2File\data\tagbase\example"

with shelve.open(path, writeback=True) as db:
    for key in list(db['tag_dict'].keys()):
        print(db['tag_dict'][key])