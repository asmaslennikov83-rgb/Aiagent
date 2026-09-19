"""Read-only WB operational statistics; timestamps are in selected business timezone."""
import asyncio
from datetime import date, datetime, timedelta
from collections import defaultdict
import httpx

BASE = 'https://statistics-api.wildberries.ru'

class WBError(Exception): pass

async def fetch_rows(token: str, endpoint: str, start: date):
    """Incremental pagination by lastChangeDate, with hard caps to avoid runaway requests.
    WB statistics endpoint is intended for operational reports, not accounting.
    """
    if endpoint not in ('orders', 'sales'):
        raise ValueError('Недопустимый endpoint')
    result, since, previous = [], f'{start.isoformat()}T00:00:00', None
    async with httpx.AsyncClient(timeout=45) as client:
        for _ in range(40):
            for attempt in range(3):
                try:
                    r = await client.get(f'{BASE}/api/v1/supplier/{endpoint}', headers={'Authorization': token},params={'dateFrom':since,'flag':0})
                    if r.status_code == 429 or r.status_code >= 500:
                        if attempt < 2:
                            await asyncio.sleep(5 * (attempt + 1)); continue
                    r.raise_for_status()
                    batch = r.json()
                    if not isinstance(batch, list): raise WBError('Неожиданный формат ответа WB')
                    break
                except (httpx.HTTPError, ValueError) as e:
                    if attempt == 2: raise WBError(f'Ошибка API WB ({endpoint}): {type(e).__name__}') from e
                    await asyncio.sleep(3 * (attempt+1))
            if not batch: return result
            result.extend(batch)
            if len(batch) < 80000: return result
            last = batch[-1].get('lastChangeDate')
            if not last or last == previous: raise WBError('Пагинация WB не продвинулась; отчёт неполный')
            previous = since = last
            await asyncio.sleep(65)  # WB statistics API generally limits calls to 1/minute/token.
    raise WBError('Превышен лимит страниц; отчёт неполный')

def aggregate(rows, start: date, end: date, kind: str):
    by_item = defaultdict(lambda: {'article':'','name':'','orders':0,'amount':0.0,'returns':0})
    total = 0
    for r in rows:
        try: day = date.fromisoformat(str(r.get('date',''))[:10])
        except ValueError: continue
        if day < start or day > end: continue
        if kind == 'orders' and r.get('isCancel'): continue
        article = str(r.get('supplierArticle') or r.get('nmId') or 'неизвестно')
        x = by_item[article]
        x['article'],x['name'] = article,str(r.get('subject') or '')[:90]
        if kind == 'sales' and str(r.get('saleID') or '').startswith('R'):
            x['returns'] += 1
            continue
        x['orders'] += 1
        # Operational amount; NOT financial payout, may be temporarily zero.
        try: x['amount'] += float(r.get('finishedPrice') or 0)
        except (ValueError, TypeError): pass
        total += 1
    items = sorted(by_item.values(),key=lambda v:(-v['orders'],v['article']))
    return {'type':kind,'period':f'{start} — {end}','count':total,'amount_finishedPrice':round(sum(x['amount'] for x in items),2), 'returns':sum(x['returns'] for x in items),'items':items[:30], 'item_count':len(items),'note':'Оперативная статистика WB (не бухгалтерская выручка); сумма finishedPrice может отличаться от ЛК. Возвраты указаны отдельно, суммы возвратов не вычитались.'}

async def report(token, kind, start, end):
    if kind not in ('orders','sales'): raise ValueError('Допустимо orders или sales')
    if end < start or end >= date.today()+timedelta(days=2) or (end-start).days > 89:
        raise ValueError('Допустимый период: до 90 дней, начало не позже конца')
    rows = await fetch_rows(token,kind,start)
    return aggregate(rows,start,end,kind)
