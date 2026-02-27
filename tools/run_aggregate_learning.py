import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.learning_aggregator import aggregate

res = aggregate()
print('Aggregated entries:', len(res))
for k,v in list(res.items())[:10]:
    print(k, '->', v)
