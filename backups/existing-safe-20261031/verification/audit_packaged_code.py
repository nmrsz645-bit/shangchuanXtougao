from __future__ import annotations
import ast
import dis
import hashlib
import json
import marshal
import sys
import types
import zipfile
import os
import pefile
from datetime import datetime, timezone
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DIST = ROOT / '候选发布-1.0.17-20261028' / 'dist' / '上传投稿中心'
EXE = DIST / '上传投稿中心.exe'
archive = CArchiveReader(str(EXE))
pyz = archive.open_embedded_archive('PYZ.pyz')

# Every immutable code field is compared; only co_filename is deliberately ignored.
CODE_FIELDS = ('co_argcount', 'co_posonlyargcount', 'co_kwonlyargcount', 'co_nlocals',
 'co_stacksize', 'co_flags', 'co_code', 'co_consts', 'co_names', 'co_varnames',
 'co_name', 'co_qualname', 'co_firstlineno', 'co_linetable', 'co_exceptiontable',
 'co_freevars', 'co_cellvars')
def canonical(obj):
    if isinstance(obj, types.CodeType):
        return {'type': 'code', 'fields': {k: canonical(getattr(obj, k)) for k in CODE_FIELDS}}
    if isinstance(obj, bytes):
        return {'type': 'bytes', 'hex': obj.hex()}
    if isinstance(obj, tuple):
        return {'type': 'tuple', 'items': [canonical(x) for x in obj]}
    if isinstance(obj, frozenset):
        vals = [canonical(x) for x in obj]
        return {'type': 'frozenset', 'items': sorted(vals, key=lambda x: json.dumps(x, sort_keys=True))}
    if obj is Ellipsis:
        return {'type': 'ellipsis'}
    if isinstance(obj, complex):
        return {'type': 'complex', 'repr': repr(obj)}
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return {'type': type(obj).__name__, 'value': obj}
    raise TypeError(type(obj))
def fingerprint(code):
    raw = json.dumps(canonical(code), sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()
def walk(code):
    yield code
    for value in code.co_consts:
        if isinstance(value, types.CodeType):
            yield from walk(value)
def strings(code):
    result = []
    for item in walk(code):
        result += [x for x in item.co_consts if isinstance(x, str)]
    return result

def compare(name, source, packaged):
    current = compile(source.read_bytes(), str(source), 'exec', dont_inherit=True, optimize=0)
    old_nodes, new_nodes = list(walk(packaged)), list(walk(current))
    detailed = []
    for i in range(max(len(old_nodes), len(new_nodes))):
        p = old_nodes[i] if i < len(old_nodes) else None
        s = new_nodes[i] if i < len(new_nodes) else None
        row = {'index': i, 'packaged_qualname': p.co_qualname if p else None,
               'source_qualname': s.co_qualname if s else None,
               'equal_ignoring_filename': bool(p and s and canonical(p) == canonical(s)),
               'packaged_sha256': fingerprint(p) if p else None,
               'source_sha256': fingerprint(s) if s else None}
        if p and s:
            row['differing_fields'] = [k for k in CODE_FIELDS if canonical(getattr(p,k)) != canonical(getattr(s,k))]
        detailed.append(row)
    return {'name': name, 'source': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'packaged_code_count': len(old_nodes), 'source_code_count': len(new_nodes),
            'equal_ignoring_filename': canonical(packaged) == canonical(current),
            'packaged_normalized_sha256': fingerprint(packaged), 'source_normalized_sha256': fingerprint(current),
            'code_objects': detailed}

comparisons=[]
for name in sorted(pyz.toc):
    source=None
    for prefix, folder in [('video_feishu', ROOT/'自动上传/src/video_feishu'),
                           ('desktop_posting', ROOT/'API投稿2.0/app/desktop_posting')]:
        if name == prefix:
            source=folder/'__init__.py'
        elif name.startswith(prefix+'.'):
            source=folder.joinpath(*name[len(prefix)+1:].split('.')).with_suffix('.py')
        if source:
            if not source.is_file():
                source = source.with_suffix('')/'__init__.py'
            break
    if name in ('center_startup','daily_restart','shared_feishu'):
        source=ROOT/(name+'.py')
    if source and source.is_file():
        comparisons.append(compare(name, source, pyz.extract(name)))
entry = marshal.loads(archive.extract('投稿中心'))
comparisons.append(compare('entry:投稿中心', ROOT/'投稿中心.py', entry))

uploader=pyz.extract('video_feishu.uploader')
uploader_nodes={c.co_qualname:c for c in walk(uploader)}
uploader_literals=strings(uploader)
expected_methods=['_require_unselected_iaa','_confirm_iaa_materials','_wait_for_result','_dialog_all_uploaded',
                  '_prepare_confirm_receipts','_capture_confirm_response','_verify_receipt_material','_upload_batch']
function_checks={name:any(k.endswith('.'+name) for k in uploader_nodes) for name in expected_methods}
required_strings={
 'actual_modal_class': 'material-center-v2-modal',
 'half_selected_css': 'material-center-v2-checkbox--indeterminate',
 'half_selected_property': 'element.indeterminate',
 'dialog_title_pattern': 'IAA',
 'completion_literal': '上传完成',
 'receipt_literal': '按平台回执及素材ID核验成功',
}
literal_checks={name:{'needle':needle,'present':any(needle in s for s in uploader_literals)}
                for name,needle in required_strings.items()}

version_node=next(c for c in walk(entry) if c.co_qualname=='app_version')
version_function=types.FunctionType(version_node, {'Path':Path, 'json':json}, 'app_version')
fixture=OUT/'version-fixture'
fixture.mkdir(exist_ok=True)
(fixture/'API投稿2.0').mkdir(exist_ok=True)
(fixture/'version.json').write_text('{"version":"1.0.17"}',encoding='utf-8')
(fixture/'API投稿2.0/version.json').write_text('{"version":"0.0.1-old"}',encoding='utf-8')
priority_result=version_function(fixture)
(fixture/'version.json').write_text('{"invalid":true}',encoding='utf-8')
fallback_result=version_function(fixture)
version_checks={'top_level_priority_result':priority_result,'top_level_priority_pass':priority_result=='1.0.17',
                'legacy_fallback_result':fallback_result,'legacy_fallback_pass':fallback_result=='0.0.1-old',
                'co_consts_strings':strings(version_node)}
with (OUT/'app-version-disassembly.txt').open('w',encoding='utf-8') as stream:
    dis.dis(version_node,file=stream)

required_modules=['video_feishu.app','video_feishu.uploader','video_feishu.config','video_feishu.feishu',
 'video_feishu.models','video_feishu.service','video_feishu.automation','video_feishu.video_ops',
 'video_feishu.tracking','desktop_posting.desktop_app','desktop_posting.single_instance',
 'desktop_posting.qianchuan_client','desktop_posting.storage','keyring','keyring.backends.Windows',
 'win32ctypes.pywin32.win32cred','win32ctypes.core.ctypes._authentication','win32ctypes.core.ctypes._dll',
 'win32ctypes.core.ctypes._common','win32ctypes.core.ctypes._time','playwright.sync_api',
 'playwright._impl._driver','playwright._impl._connection','playwright._impl._transport',
 'greenlet','pyee','tkinter','sqlite3','hashlib','json','urllib.request','_collections_abc']
with zipfile.ZipFile(DIST/'_internal/base_library.zip') as base_lib:
    base_names=set(base_lib.namelist())
module_locations={name:('PYZ' if name in pyz.toc else 'base_library.zip' if name.replace('.', '/')+'.pyc' in base_names or name.replace('.', '/')+'/__init__.pyc' in base_names else None) for name in required_modules}
module_checks={name:location is not None for name,location in module_locations.items()}
required_files=['python313.dll','_tkinter.pyd','tcl86t.dll','tk86t.dll','_sqlite3.pyd','_ssl.pyd',
 '_hashlib.pyd','_ctypes.pyd','playwright/driver/node.exe','playwright/driver/package/cli.js','keyring-25.7.0.dist-info/entry_points.txt','playwright-1.62.0.dist-info/METADATA']
file_checks={p:(DIST/'_internal'/p).is_file() for p in required_files}
file_checks.update({'_tcl_data':(DIST/'_internal/_tcl_data').is_dir(),
 '_tk_data':(DIST/'_internal/_tk_data').is_dir(),
 'greenlet_extension':any((DIST/'_internal/greenlet').glob('_greenlet*.pyd'))})
# Read PE import tables without loading or executing packaged native binaries.
system_root=Path(os.environ.get('SystemRoot',r'C:\Windows'))
pe_reports=[]
for binary in sorted(DIST.rglob('*')):
    if binary.suffix.lower() not in ('.dll','.pyd','.exe') or not binary.is_file():
        continue
    pe=pefile.PE(str(binary),fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
    imports=[entry.dll.decode('ascii') for entry in getattr(pe,'DIRECTORY_ENTRY_IMPORT',[])]
    missing=[]
    for dep in imports:
        if dep.lower().startswith(('api-ms-win-','ext-ms-')):
            continue
        choices=[binary.parent/dep,DIST/dep,DIST/'_internal'/dep,system_root/'System32'/dep]
        if not any(p.is_file() for p in choices):
            missing.append(dep)
    pe_reports.append({'path':binary.relative_to(DIST).as_posix(),'imports':imports,'unresolved_imports':missing})
    pe.close()
unresolved_pe=[r for r in pe_reports if r['unresolved_imports']]
# Avoid loading a keyring backend or accessing any OS credential store.
warning_file=ROOT/'候选发布-1.0.17-20261028/build/上传投稿中心/warn-上传投稿中心.txt'
warning_text=warning_file.read_text(encoding='utf-8')
relevant_warnings=[line for line in warning_text.splitlines() if any(x in line for x in ('video_feishu','desktop_posting','playwright','keyring','win32ctypes','win32cred','pywintypes','cffi','collections.abc'))]
report={'created_utc':datetime.now(timezone.utc).isoformat(),'mode':'offline-static-archive-inspection-no-exe-launch',
 'python':sys.version,'exe':str(EXE),'exe_sha256':hashlib.sha256(EXE.read_bytes()).hexdigest(),
 'compared_fields_ignoring_only_co_filename':list(CODE_FIELDS),'module_comparisons':comparisons,
 'all_local_code_matches':all(c['equal_ignoring_filename'] for c in comparisons),
 'total_compared_code_objects':sum(c['packaged_code_count'] for c in comparisons),
 'uploader_function_checks':function_checks,'uploader_literal_checks':literal_checks,
 'app_version_checks':version_checks,'required_modules_present':module_checks,'module_locations':module_locations,'required_binary_and_data_files':file_checks,'pe_import_audit':pe_reports,'unresolved_pe_imports':unresolved_pe,
 'relevant_build_warnings':relevant_warnings,
 'limitations':['No GUI, EXE, browser, posting, upload, network, user configuration, or credential store was accessed.',
 'Static archive inspection does not establish real browser interaction or frozen-process runtime startup.']}
(OUT/'packaged-code-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
failed_modules=[c['name'] for c in comparisons if not c['equal_ignoring_filename']]
failed_checks={k:v for k,v in literal_checks.items() if not v['present']}
summary={'evidence':str(OUT/'packaged-code-audit.json'),'compared_modules':len(comparisons),
 'total_code_objects':report['total_compared_code_objects'],'all_local_code_matches':report['all_local_code_matches'],
 'failed_module_matches':failed_modules,'uploader_functions':function_checks,'uploader_literal_failures':failed_checks,
 'version_checks':version_checks,'missing_pyz_modules':[n for n,v in module_checks.items() if not v],
 'missing_binary_or_data_files':[n for n,v in file_checks.items() if not v],'pe_files_inspected':len(pe_reports),'unresolved_pe_imports':unresolved_pe}
print(json.dumps(summary,ensure_ascii=True,indent=2))
if unresolved_pe or failed_modules or failed_checks or not all(function_checks.values()) or not all(module_checks.values()) or not all(file_checks.values()) or not version_checks['top_level_priority_pass'] or not version_checks['legacy_fallback_pass']:
    raise SystemExit(1)