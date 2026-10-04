"""Bounded, evidence-grounded recovery proposals; never verification proofs."""
from __future__ import annotations
import json

from agi_core.mission_protocol import tool_response_schema, validate_args, validate_checks


RECOVERY_FIELDS = {'request_quote', 'evidence_ids', 'hypothesis',
                   'expected_observation', 'next_action'}


def recovery_response_schema(criteria, allowed, evidence_ids, explicit_tools):
    return {'type': 'object', 'properties': {
        'request_quote': {'type': 'string'},
        'evidence_ids': {'type': 'array', 'minItems': 1,
                         'items': {'type': 'string', 'enum': list(evidence_ids)}},
        'hypothesis': {'type': 'string'},
        'expected_observation': {'type': 'string'},
        'next_action': tool_response_schema(criteria, allowed,
                                            required_tool_names=explicit_tools)},
        'required': sorted(RECOVERY_FIELDS), 'additionalProperties': False}


def validate_recovery(reply, request, observations, allowed, criteria, stalled_actions):
    try:
        value = json.loads(reply)
    except (TypeError, ValueError) as exc:
        raise ValueError('Recovery must return one structured JSON proposal') from exc
    if not isinstance(value, dict) or set(value) != RECOVERY_FIELDS:
        raise ValueError('Recovery proposal fields do not match the contract')
    for field in ('request_quote', 'hypothesis', 'expected_observation'):
        if not isinstance(value[field], str) or not value[field].strip():
            raise ValueError('Recovery needs a nonempty ' + field)
    if value['request_quote'] not in request or not any(ch.isalnum() for ch in value['request_quote']):
        raise ValueError('Recovery must quote the immutable original request')
    ids = {e['id'] for e in observations}
    if (not isinstance(value['evidence_ids'], list) or not value['evidence_ids']
            or any(not isinstance(e, str) or e not in ids for e in value['evidence_ids'])):
        raise ValueError('Recovery must cite supplied observations')
    call = value['next_action']
    if (not isinstance(call, dict) or set(call) != {'tool', 'args'}
            or not isinstance(call['tool'], str) or call['tool'] not in allowed
            or not isinstance(call['args'], dict)):
        raise ValueError('Recovery action must use a permitted tool without replanning')
    validate_args(call['tool'], call['args'])
    if call['tool'] in {'verify', 'spawn_agent'}:
        validate_checks(call['args']['checks'], criteria)
    if call in stalled_actions:
        raise ValueError('Recovery must change the action instead of replaying the detected cycle')
    return value


def bounded_recovery_payload(agent, observations, stalled_actions, instructions):
    """Retain the objective/obligations/fences; clearly mark omitted observations."""
    value = {'original_request': agent.request_text,
             'criteria': [{'criterion': c, 'verified': c in agent.state['verified']}
                          for c in agent.state['criteria']],
             'required_tools': agent.state.get('required_tools', []),
             'executed_tools': agent.state.get('executed_tools', []),
             'known_resources': list(agent.state.get('resources', {}).values()),
             'interrupted_processes': agent.state.get('interrupted_processes', []),
             'stalled_actions': stalled_actions,
             'observations': [], 'observations_omitted': len(observations)}
    capacity = agent._context_chars() - len(instructions)
    encode = lambda: json.dumps(value, ensure_ascii=False)
    if len(encode()) > capacity:
        raise ValueError('Recovery context cannot retain the immutable goal and execution obligations')
    for evidence in reversed(observations):
        record = dict(evidence)
        value['observations'].insert(0, record)
        value['observations_omitted'] -= 1
        if len(encode()) <= capacity:
            continue
        result = json.dumps(record.pop('result', None), ensure_ascii=False)
        record['result_truncated'] = True
        limit = min(len(result), max(0, capacity - len(encode())))
        record['result_excerpt'] = agent._excerpt(result, limit)
        while len(encode()) > capacity and limit:
            limit //= 2
            record['result_excerpt'] = agent._excerpt(result, limit)
        if len(encode()) > capacity or not limit:
            value['observations'].pop(0)
            value['observations_omitted'] += 1
    if not value['observations']:
        raise ValueError('Recovery context cannot retain any actual observation')
    return value
