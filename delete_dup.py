import os
from pathlib import Path
import re
import pickle

def delete(path):
    pat = r'[0-9]{3}x[0-9]{3}(?=\.jpeg)'
    for root, dirs, files in os.walk(path):
        for file in files:
            p = Path(root, file)
            if re.search(pat, file):
                print(p)
                # os.remove(p)


if __name__ == '__main__':

    set = {'https://dwkm.xyz/school/13550.html',
           'https://dwkm.xyz/school/13549.html',
           'https://dwkm.xyz/school/13542.html',
           'https://dwkm.xyz/school/13541.html',
           'https://dwkm.xyz/school/13540.html',
           }

    with open('dwkm.url.pickle', 'rb') as f:
        data = pickle.load(f)
        print(len(data))


