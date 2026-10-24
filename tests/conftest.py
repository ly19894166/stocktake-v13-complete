import copy
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from core import import_pair
from synthetic_data import simulated_pair

@pytest.fixture(scope='session')
def sample():
    gain,loss=simulated_pair()
    items,notes,fp=import_pair(gain,loss)
    return items,notes,fp,{'盘盈':gain,'盘亏':loss}

@pytest.fixture
def items(sample):return copy.deepcopy(sample[0])

@pytest.fixture
def store(tmp_path):
    from storage import Store
    value=Store(tmp_path/'data')
    yield value
    value.close()

@pytest.fixture
def batch(store,sample):
    return store.create(*sample[:3],'模拟门店甲','模拟盘点期间',sample[3])
