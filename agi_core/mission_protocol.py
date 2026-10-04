"""Tool argument contracts shared by constrained decoding and execution."""
from __future__ import annotations
from copy import deepcopy


TEXT = {'type':'string'}
STRINGS = {'type':'array','items':TEXT}
NONEMPTY_STRINGS = {**STRINGS,'minItems':1}
INTEGER = {'type':'integer'}


def object_args(properties, required=()):
    return {'type':'object','properties':properties,'required':list(required),'additionalProperties':False}


CHECK_SCHEMA = {'anyOf':[
    object_args({'kind':{'const':'file'},'path':TEXT,'min_bytes':INTEGER,'sha256':TEXT,'criterion':TEXT},('kind','path')),
    object_args({'kind':{'const':'text'},'path':TEXT,'equals':TEXT,'contains':TEXT,'criterion':TEXT},('kind','path')),
    object_args({'kind':{'const':'json'},'path':TEXT,'equals':{'description':'Expected complete JSON value; object key sets and values must match exactly.'},
                 'keys':{**STRINGS,'description':'Complete exact object key set, not a subset.'},
                 'types':{'type':'object','additionalProperties':{'type':'string','enum':['integer','number','string','boolean','object','array','null']}},
                 'criterion':TEXT},('kind','path')),
    object_args({'kind':{'const':'command'},'argv':NONEMPTY_STRINGS,'contains':TEXT,'expected_exit_code':INTEGER,'criterion':TEXT},('kind','argv')),
    object_args({'kind':{'const':'source'},'evidence_ids':NONEMPTY_STRINGS,'criterion':TEXT},('kind','evidence_ids')),
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
    'spawn_agent':object_args({'task':TEXT,'tasks':NONEMPTY_STRINGS,'agent':TEXT}),
    'create_agent':object_args({'name':TEXT,'role':TEXT},('name','role')),
    'create_skill':object_args({'name':TEXT,'description':TEXT,'instructions':TEXT},('name','description','instructions')),
    'list_skills':object_args({}),
    'verify':object_args({'checks':{'type':'array','items':CHECK_SCHEMA,'minItems':1}},('checks',)),
    'finish':object_args({'message':TEXT,'status':{'type':'string','enum':['completed','blocked']}},('message',)),
}
ARG_SCHEMAS['run_command']['oneOf'] = [{'required':['argv']},{'required':['command']}]
ARG_SCHEMAS['spawn_agent']['oneOf'] = [{'required':['task']},{'required':['tasks']}]

TOOL_RESPONSE_SCHEMA = {
    'type':'object','properties':{'tool':{'type':'string','enum':list(ARG_SCHEMAS)},'args':{'type':'object'}},
    'required':['tool','args'],'additionalProperties':False,
    'anyOf':[{'properties':{'tool':{'const':name},'args':schema}} for name,schema in ARG_SCHEMAS.items()],
}
CHECK_FIELDS = {branch['properties']['kind']['const']:set(branch['properties']) for branch in CHECK_SCHEMA['anyOf']}


def tool_response_schema(criteria=(), allowed=None):
    selected = list(ARG_SCHEMAS) if allowed is None else [name for name in ARG_SCHEMAS if name in allowed]
    schema = deepcopy(TOOL_RESPONSE_SCHEMA)
    schema['properties']['tool']['enum'] = selected
    schema['anyOf'] = [branch for branch in schema['anyOf'] if branch['properties']['tool']['const'] in selected]
    verify = next(branch['properties']['args'] for branch in schema['anyOf'] if branch['properties']['tool']['const']=='verify')
    checks = verify['properties']['checks']['items']['anyOf']
    if allowed is not None and 'run_command' not in allowed:
        checks[:] = [branch for branch in checks if branch['properties']['kind']['const']!='command']
    if criteria:
        for branch in checks:
            branch['properties']['criterion'] = {'type':'string','enum':list(criteria)}
            branch['required'].append('criterion')
    return schema


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
