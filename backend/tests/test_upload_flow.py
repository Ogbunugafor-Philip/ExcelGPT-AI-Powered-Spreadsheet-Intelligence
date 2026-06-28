from pathlib import Path

import pandas as pd

from services.excel_reader import ExcelReader
from services.data_profiler import DataProfiler


def test_excel_reader_profiles_basic_sheet(tmp_path):
    file_path = tmp_path / 'sample.xlsx'
    df = pd.DataFrame(
        {
            'branch_code': ['BR001', 'BR002'],
            'deposits_ngn': [154000000, 98700000],
            'month': ['2026-01', '2026-02'],
        }
    )
    with pd.ExcelWriter(file_path) as writer:
        df.to_excel(writer, sheet_name='Branch Deposits', index=False)

    reader = ExcelReader()
    result = reader.read_file(str(file_path))

    assert result['sheets'][0]['name'] == 'Branch Deposits'
    assert result['sheets'][0]['row_count'] == 2
    assert len(result['sheets'][0]['rows']) == 2
    assert result['sheets'][0]['columns'][0] == 'branch_code'

    profiler = DataProfiler()
    brief = profiler.generate_intelligence_brief(
        {'Branch Deposits': profiler.profile(df, 'Branch Deposits')},
        'sample.xlsx',
    )
    assert brief['total_sheets'] == 1
    # 'branch_code' and 'deposits_ngn' trip the Nigerian-context detector ('branch', 'ngn').
    assert brief['nigerian_context']['detected'] is True
