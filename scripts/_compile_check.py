import py_compile, sys
files = ['core/views_conversor.py','core/urls.py']
ok = True
print('Compiling files:')
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f + ' OK')
    except Exception as e:
        print('ERROR compiling', f, ':', e)
        ok = False
sys.exit(0 if ok else 1)
