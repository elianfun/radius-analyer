def fix_encoding(value):
    """latin1 欄位中儲存的 UTF-8 位元組轉回正確字串"""
    if value is None:
        return None
    try:
        return value.encode('latin1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def fix_row(row: dict, fields=('description',)) -> dict:
    """對指定欄位套用 fix_encoding"""
    return {k: (fix_encoding(v) if k in fields else v) for k, v in row.items()}
