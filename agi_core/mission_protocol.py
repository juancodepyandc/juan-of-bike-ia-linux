"""Tool argument contracts shared by constrained decoding and execution."""
from __future__ import annotations
from copy import deepcopy
import json
from agi_core.json_predicates import parse_json_expression


TEXT = {'type':'string'}
STRINGS = {'type':'array','items':TEXT}
NONEMPTY_STRINGS = {**STRINGS,'minItems':1}
INTEGER = {'type':'integer'}
PURE_CHECKS = {'file','text','json','csv_json','agent','skill','delegation'}


def object_args(properties, required=()):
    return {'type':'object','properties':properties,'required':list(required),'additionalProperties':False}


CHECK_SCHEMA = {'anyOf':[
    object_args({'kind':{'const':'file'},'path':TEXT,'min_bytes':INTEGER,'sha256':TEXT,'criterion':TEXT},('kind','path')),
    object_args({'kind':{'const':'text'},'path':TEXT,'equals':TEXT,'contains':TEXT,'criterion':TEXT},('kind','path')),
    object_args({'kind':{'const':'json'},'path':TEXT,'equals':{'description':'Expected complete JSON value; object key sets and values must match exactly.'},
                 'keys':{**STRINGS,'description':'Complete exact object key set. Structural proof only; does not prove calculations or constraints.'},
                 'types':{'type':'object','additionalProperties':{'type':'string','enum':['integer','number','string','boolean','object','array','null']},'description':'Field types only; not proof of calculations or value relations.'},
                 'expressions':{**NONEMPTY_STRINGS,'description':'Boolean predicates evaluated on the actual saved JSON named data. Supports field/array subscripts, numeric arithmetic, comparisons and boolean logic. No calls or attributes. Use actual request parameters for relations; use command assertions for complex or optimality proofs.'},
                 'criterion':TEXT},('kind','path')),
    object_args({'kind':{'const':'command'},'argv':NONEMPTY_STRINGS,'contains':TEXT,'expected_exit_code':INTEGER,'criterion':TEXT},('kind','argv')),
    object_args({'kind':{'const':'source'},'evidence_ids':NONEMPTY_STRINGS,'criterion':TEXT},('kind','evidence_ids')),
    object_args({'kind':{'const':'csv_json'},'path':{**TEXT,'description':'CSV input file, read without mutation.'},
                 'json_path':{**TEXT,'description':'Saved aggregate JSON file; its values are checked against the actual CSV.'},
                 'row_field':{**TEXT,'description':'JSON key for the number of CSV data rows.'},
                 'sum_fields':{'type':'object','additionalProperties':TEXT,'description':'Map each JSON sum key to the CSV integer column it aggregates.'},
                 'delimiter':TEXT,'source_sha256':TEXT,'criterion':TEXT},
                ('kind','path','json_path','row_field','sum_fields')),
    object_args({'kind':{'const':'agent'},'name':TEXT,'criterion':TEXT},('kind','name')),
    object_args({'kind':{'const':'delegation'},'agent':TEXT,'tasks':NONEMPTY_STRINGS,
                 'execution_id':TEXT,'criterion':TEXT},('kind','agent')),
    object_args({'kind':{'const':'skill'},'name':TEXT,'criterion':TEXT},('kind','name')),
]}


ARG_SCHEMAS = {
    'inspect_runtime':object_args({}),
    'set_plan':object_args({'steps':NONEMPTY_STRINGS,'criteria':NONEMPTY_STRINGS},('steps','criteria')),
    'list_files':object_args({'path':TEXT}),
    'read_file':object_args({'path':TEXT,'offset':INTEGER,'limit':INTEGER},('path',)),
    'inspect_csv':object_args({'path':TEXT,'integer_columns':STRINGS,'delimiter':TEXT},('path',)),
    'write_file':object_args({'path':TEXT,'content':TEXT,'expected_sha256':TEXT},('path','content')),
    'run_command':object_args({'argv':NONEMPTY_STRINGS,'command':TEXT}),
    'list_tools':object_args({'query':TEXT}),
    'inspect_tool':object_args({'name':TEXT},('name',)),
    'run_tool':object_args({'name':TEXT,'argv':STRINGS},('name',)),
    'create_tool':object_args({'name':TEXT,'code':TEXT},('name','code')),
    'generate_image':object_args({'prompt':TEXT,'folder':TEXT},('prompt',)),
    'search_web':object_args({'query':TEXT},('query',)),
    'fetch_url':object_args({'url':TEXT},('url',)),
    'spawn_agent':object_args({'task':TEXT,'tasks':NONEMPTY_STRINGS,'agent':TEXT,
                             'checks':{'type':'array','items':CHECK_SCHEMA,'minItems':1}},('checks',)),
    'create_agent':object_args({'name':TEXT,'role':TEXT},('name','role')),
    'create_skill':object_args({'name':TEXT,'description':TEXT,'instructions':TEXT},('name','description','instructions')),
    'list_skills':object_args({}),
    'verify':object_args({'checks':{'type':'array','items':CHECK_SCHEMA,'minItems':1}},('checks',)),
    'finish':object_args({'message':TEXT,'status':{'type':'string','enum':['completed','blocked']}},('message',)),
}
ARG_SCHEMAS['run_command']['oneOf'] = [{'required':['argv']},{'required':['command']}]
ARG_SCHEMAS['spawn_agent']['oneOf'] = [{'required':['task']},{'required':['tasks']}]
ARG_SCHEMAS['set_plan']['properties']['required_tools'] = {'type':'array','items':{'type':'string','enum':[
    name for name in ARG_SCHEMAS if name not in {'set_plan','verify','finish'}]}}

CHECK_FIELDS = {branch['properties']['kind']['const']:set(branch['properties']) for branch in CHECK_SCHEMA['anyOf']}

TOOL_DESCRIPTIONS = {
    'create_skill':'Save a project skill once. If it exists, inspect list_skills and verify kind=skill with its name; do not recreate it to prove its existence.',
    'create_agent':'Save a reusable role once. Verify kind=agent with its name to check the actual saved definition; existence does not prove execution.',
    'spawn_agent':'Execute a delegated task using an optional saved role and concrete parent acceptance checks. The parent verifies the saved outputs after worker completion.',
    'list_skills':'List discovered skills with their actual file paths and byte hashes. This is discovery, not proof of successful execution.',
    'verify':'Run explicit checks bound to exact current criteria. JSON expressions check saved value relations; keys/types only check structure. skill and agent check saved definitions; delegation checks an actual completed worker run using the specified role; csv_json compares saved aggregates to the actual input.',
    'list_tools':'Discover permitted built-in protocol tools and Python scripts. Built-ins are called directly; scripts use run_tool after inspecting their arguments.',
    'inspect_tool':'Inspect a built-in argument contract or a Python script without running it.',
}


def audit_response_schema(criteria, allowed, inventory, *, max_chars, allow_delegation_checks=True):
    """Bind flat integer CSV aggregate output names to observed schemas."""
    schema = tool_response_schema(criteria,allowed,allow_delegation_checks=allow_delegation_checks)
    schema['oneOf'] = [b for b in schema['oneOf'] if b['properties']['tool']['const']=='verify']
    checks = schema['oneOf'][0]['properties']['args']['properties']['checks']['items']['anyOf']
    csv_branch = next(b for b in checks if b['properties']['kind']['const']=='csv_json')
    variants = []
    for info in inventory:
        fields = info.get('json_fields',{})
        if len(fields)<2 or any(t!='integer' or not key.strip() for key,t in fields.items()):
            continue
        for row in fields:
            variant = deepcopy(csv_branch)
            properties = variant['properties']
            properties['json_path'] = {'const':info['path']}
            properties['row_field'] = {'const':row}
            sums = [key for key in fields if key!=row]
            properties['sum_fields'] = object_args({key:TEXT for key in sums},sums)
            variants.append(variant)
            # Large schemas fall back to ordinary decoding plus execution-time
            # preflight. This is an explicit resource bound, not a quality score.
            if len(json.dumps(variants,ensure_ascii=False))>max_chars:
                return schema
    if variants:
        checks[:] = [b for b in checks if b is not csv_branch]+variants
        if len(json.dumps(schema,ensure_ascii=False))>max_chars:
            checks[:] = [b for b in checks if b not in variants]+[csv_branch]
    return schema


def tool_response_schema(criteria=(), allowed=None, *, required_tool_names=None, allow_delegation_checks=True):
    selected = list(ARG_SCHEMAS) if allowed is None else [name for name in ARG_SCHEMAS if name in allowed]
    alternatives = []
    for name in selected:
        args = deepcopy(ARG_SCHEMAS[name])
        if name=='set_plan':
            args['required'].append('required_tools')
            names = [n for n in selected if n not in {'set_plan','verify','finish'}
                     and (required_tool_names is None or n in required_tool_names)]
            args['properties']['required_tools'] = ({'type':'array','items':{'type':'string','enum':names}} if names else {'const':[]})
        if name in {'verify','spawn_agent'}:
            checks = args['properties']['checks']['items']['anyOf']
            if name=='spawn_agent' or not allow_delegation_checks:
                checks[:] = [branch for branch in checks if branch['properties']['kind']['const']!='delegation']
            if allowed is not None and 'run_command' not in allowed:
                checks[:] = [branch for branch in checks if branch['properties']['kind']['const']!='command']
            concrete = []
            for branch in checks:
                kind = branch['properties']['kind']['const']
                expectations = {'text':('equals','contains'),'json':('equals','keys','types','expressions')}.get(kind)
                if expectations:
                    for field in expectations:
                        variant = deepcopy(branch)
                        variant['required'].append(field)
                        concrete.append(variant)
                else:
                    concrete.append(branch)
            checks[:] = concrete
            if criteria:
                for branch in checks:
                    branch['properties']['criterion'] = {'type':'string','enum':list(criteria)}
                    branch['required'].append('criterion')
        choices = args.pop('oneOf',None)
        if choices:
            exclusive = {key for choice in choices for key in choice['required']}
            variants = []
            for choice in choices:
                variant = deepcopy(args)
                variant['required'] += choice['required']
                for key in exclusive-set(choice['required']):
                    variant['properties'].pop(key)
                variants.append(variant)
        else:
            variants = [args]
        alternatives.extend(object_args({'tool':{'const':name},'args':variant},('tool','args')) for variant in variants)
    # Full alternatives avoid relying on a grammar converter composing adjacent
    # object/union constraints or required-only branches correctly.
    return {'oneOf':alternatives}


def validate_args(name, args):
    """Reject bad top-level arguments before effects; tools validate their data."""
    if name not in ARG_SCHEMAS:
        raise ValueError('Unknown tool: '+str(name))
    schema = ARG_SCHEMAS[name]
    if not isinstance(args,dict):
        raise ValueError('Tool arguments must be an object')
    unknown = set(args)-schema['properties'].keys()
    missing = set(schema['required'])-args.keys()
    if unknown or missing:
        raise ValueError(f'{name} arguments: unknown {sorted(unknown)}, missing {sorted(missing)}; accepted fields {list(schema["properties"])}')
    kinds = {'string':str,'integer':int,'array':list,'object':dict}
    for key,value in args.items():
        field = schema['properties'][key]
        if type(value) is not kinds[field['type']]:
            raise ValueError(f'{name}.{key} must be {field["type"]}')
        if 'enum' in field and value not in field['enum']:
            raise ValueError(f'{name}.{key} must be one of {field["enum"]}')
        if isinstance(value,list):
            if len(value)<field.get('minItems',0):
                raise ValueError(f'{name}.{key} must not be empty')
            if field.get('items',{}).get('type')=='string' and not all(isinstance(v,str) for v in value):
                raise ValueError(f'{name}.{key} must contain strings')
    if 'oneOf' in schema and sum(all(k in args for k in branch['required']) for branch in schema['oneOf'])!=1:
        raise ValueError(f'{name} requires exactly one of '+', '.join(branch['required'][0] for branch in schema['oneOf']))


def validate_checks(checks, criteria=()):
    """Validate a whole delegation contract before starting any worker/effect."""
    if not isinstance(checks,list) or not checks:
        raise ValueError('At least one concrete acceptance check is required')
    branches = {s['properties']['kind']['const']:s for s in CHECK_SCHEMA['anyOf']}
    kinds = {'string':str,'integer':int,'array':list,'object':dict}
    for check in checks:
        if not isinstance(check,dict) or not isinstance(check.get('kind'),str) or check['kind'] not in branches:
            raise ValueError('Unsupported acceptance check')
        schema = branches[check['kind']]
        if set(check)-schema['properties'].keys() or set(schema['required'])-check.keys():
            raise ValueError('Acceptance check fields do not match '+check['kind'])
        if criteria and check.get('criterion') not in criteria:
            raise ValueError('Every check must name an exact current criterion')
        for key,value in check.items():
            field = schema['properties'][key]
            if 'type' in field and type(value) is not kinds[field['type']]:
                raise ValueError(f'Acceptance check {key} must be {field["type"]}')
            if field.get('type')=='array' and (len(value)<field.get('minItems',0) or not all(isinstance(v,str) for v in value)):
                raise ValueError(f'Acceptance check {key} must contain strings')
            if isinstance(value,dict) and 'additionalProperties' in field:
                item = field['additionalProperties']
                if any(not isinstance(v,str) or ('enum' in item and v not in item['enum']) for v in value.values()):
                    raise ValueError(f'Acceptance check {key} has invalid field values')
        if check['kind']=='csv_json':
            if not check['row_field'] or check['row_field'] in check['sum_fields'] or any(not k or not v for k,v in check['sum_fields'].items()):
                raise ValueError('CSV JSON row/sum field mappings must be nonempty and distinct')
            if 'delimiter' in check and len(check['delimiter'])!=1:
                raise ValueError('CSV delimiter must be one character')
        if check['kind']=='text' and not {'equals','contains'}&check.keys():
            raise ValueError('Text verification requires equals or contains')
        if check['kind']=='json' and not {'equals','keys','types','expressions'}&check.keys():
            raise ValueError('JSON verification requires equals, keys, types or expressions')
        if check['kind']=='json' and 'expressions' in check:
            for expression in check['expressions']:
                parse_json_expression(expression)
        if check['kind']=='file' and check.get('min_bytes',1)<0:
            raise ValueError('min_bytes must be nonnegative')
