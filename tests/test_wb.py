from datetime import date
from wb import aggregate

def test_aggregates_no_cancelled_and_date_filter():
    r=[{'date':'2026-09-18T10:00:00','supplierArticle':'A','finishedPrice':100,'isCancel':False},
       {'date':'2026-09-18T11:00:00','supplierArticle':'A','finishedPrice':200,'isCancel':True},
       {'date':'2026-09-17T11:00:00','supplierArticle':'A','finishedPrice':300}]
    a=aggregate(r,date(2026,9,18),date(2026,9,18),'orders')
    assert a['count']==1 and a['amount_finishedPrice']==100

def test_return_separate():
    r=[{'date':'2026-09-18T10:00:00','supplierArticle':'A','saleID':'S123','finishedPrice':100},
       {'date':'2026-09-18T11:00:00','supplierArticle':'A','saleID':'R123','finishedPrice':100}]
    a=aggregate(r,date(2026,9,18),date(2026,9,18),'sales')
    assert a['count']==1 and a['returns']==1 and a['amount_finishedPrice']==100
