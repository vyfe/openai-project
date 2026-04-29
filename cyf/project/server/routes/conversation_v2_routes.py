from flask import Blueprint, Response

from dto.conversation_dto import (
    DTOError,
    parse_add_remove_model,
    parse_create_master,
    parse_legacy_migrate,
    parse_master_delete,
    parse_master_id,
    parse_pagination,
    parse_retry_cell,
    parse_round_send,
    parse_stream_cell,
)
from services import conversation_service, legacy_migration_service, retry_service, round_execution_service, cell_stream_service

conversation_v2_bp = Blueprint('conversation_v2', __name__)


# 由 server.py 注入，避免循环导入
require_auth_decorator = None
get_request_data_func = None


def setup_conversation_v2(require_auth, get_request_data):
    global require_auth_decorator, get_request_data_func
    require_auth_decorator = require_auth
    get_request_data_func = get_request_data


def _resp_ok(data=None, msg=''):
    return {'success': True, 'msg': msg, 'data': data or {}}, 200


def _resp_fail(msg, code=200):
    return {'success': False, 'msg': msg}, code


def _with_auth(handler):
    if require_auth_decorator is None:
        raise RuntimeError('conversation_v2 routes not initialized: setup_conversation_v2 not called')
    return require_auth_decorator(handler)


@conversation_v2_bp.route('/never_guess_my_usage/conversation/master/create', methods=['POST'])
def master_create_entry():
    @_with_auth
    def _handler(user, password):
        try:
            data = get_request_data_func()
            payload = parse_create_master(data)
            result = conversation_service.create_master(
                owner=user,
                title=payload['title'],
                session_type=payload['session_type'],
                active_models=payload['active_models'],
            )
            return _resp_ok(result)
        except DTOError as e:
            return _resp_fail(str(e))
        except conversation_service.ConversationError as e:
            return _resp_fail(str(e))
        except Exception as e:
            return _resp_fail(f'create master failed: {str(e)}')

    return _handler()


@conversation_v2_bp.route('/never_guess_my_usage/conversation/master/list', methods=['POST'])
def master_list_entry():
    @_with_auth
    def _handler(user, password):
        try:
            data = get_request_data_func()
            page_payload = parse_pagination(data)
            result = conversation_service.list_master(
                owner=user,
                page=page_payload['page'],
                page_size=page_payload['page_size'],
            )
            return _resp_ok(result)
        except DTOError as e:
            return _resp_fail(str(e))
        except Exception as e:
            return _resp_fail(f'list master failed: {str(e)}')

    return _handler()


@conversation_v2_bp.route('/never_guess_my_usage/conversation/master/detail', methods=['POST'])
def master_detail_entry():
    @_with_auth
    def _handler(user, password):
        try:
            data = get_request_data_func()
            payload = parse_master_id(data)
            result = conversation_service.get_master_detail(owner=user, master_id=payload['master_id'])
            return _resp_ok(result)
        except DTOError as e:
            return _resp_fail(str(e))
        except conversation_service.ConversationError as e:
            return _resp_fail(str(e))
        except Exception as e:
            return _resp_fail(f'get detail failed: {str(e)}')

    return _handler()


@conversation_v2_bp.route('/never_guess_my_usage/conversation/master/add_model', methods=['POST'])
def master_add_model_entry():
    @_with_auth
    def _handler(user, password):
        try:
            data = get_request_data_func()
            payload = parse_add_remove_model(data)
            result = conversation_service.add_model(owner=user, master_id=payload['master_id'], model_id=payload['model_id'])
            return _resp_ok(result)
        except DTOError as e:
            return _resp_fail(str(e))
        except conversation_service.ConversationError as e:
            return _resp_fail(str(e))
        except Exception as e:
            return _resp_fail(f'add model failed: {str(e)}')

    return _handler()


@conversation_v2_bp.route('/never_guess_my_usage/conversation/master/remove_model', methods=['POST'])
def master_remove_model_entry():
    @_with_auth
    def _handler(user, password):
        try:
            data = get_request_data_func()
            payload = parse_add_remove_model(data)
            result = conversation_service.remove_model(owner=user, master_id=payload['master_id'], model_id=payload['model_id'])
            return _resp_ok(result)
        except DTOError as e:
            return _resp_fail(str(e))
        except conversation_service.ConversationError as e:
            return _resp_fail(str(e))
        except Exception as e:
            return _resp_fail(f'remove model failed: {str(e)}')

    return _handler()


@conversation_v2_bp.route('/never_guess_my_usage/conversation/master/delete', methods=['POST'])
def master_delete_entry():
    @_with_auth
    def _handler(user, password):
        try:
            data = get_request_data_func()
            payload = parse_master_delete(data)
            result = conversation_service.delete_masters(owner=user, master_ids=payload['master_ids'])
            return _resp_ok(result)
        except DTOError as e:
            return _resp_fail(str(e))
        except conversation_service.ConversationError as e:
            return _resp_fail(str(e))
        except Exception as e:
            return _resp_fail(f'delete master failed: {str(e)}')

    return _handler()


@conversation_v2_bp.route('/never_guess_my_usage/conversation/round/send', methods=['POST'])
def round_send_entry():
    @_with_auth
    def _handler(user, password):
        try:
            data = get_request_data_func()
            payload = parse_round_send(data)

            round_data = conversation_service.create_round(
                owner=user,
                master_id=payload['master_id'],
                user_prompt=payload['user_prompt'],
                attachments=payload['attachments'],
            )

            fanout = round_execution_service.execute_round_fanout(
                user=user,
                master_id=payload['master_id'],
                round_id=round_data['round']['round_id'],
                user_prompt=payload['user_prompt'],
                children=round_data['children'],
                system_prompt_id=payload['system_prompt_id'],
                max_response_tokens=payload['max_response_tokens'],
            )

            return _resp_ok(
                {
                    'round': round_data['round'],
                    'cells': fanout['cells'],
                }
            )
        except DTOError as e:
            return _resp_fail(str(e))
        except conversation_service.ConversationError as e:
            return _resp_fail(str(e))
        except Exception as e:
            return _resp_fail(f'send round failed: {str(e)}')

    return _handler()


@conversation_v2_bp.route('/never_guess_my_usage/conversation/round/create', methods=['POST'])
def round_create_entry():
    @_with_auth
    def _handler(user, password):
        try:
            data = get_request_data_func()
            payload = parse_round_send(data)
            round_data = conversation_service.create_round(
                owner=user,
                master_id=payload['master_id'],
                user_prompt=payload['user_prompt'],
                attachments=payload['attachments'],
            )
            return _resp_ok(
                {
                    'round': round_data['round'],
                    'cells': round_data['cells'],
                    'children': round_data['children'],
                }
            )
        except DTOError as e:
            return _resp_fail(str(e))
        except conversation_service.ConversationError as e:
            return _resp_fail(str(e))
        except Exception as e:
            return _resp_fail(f'create round failed: {str(e)}')

    return _handler()


@conversation_v2_bp.route('/never_guess_my_usage/conversation/cell/stream', methods=['POST'])
def cell_stream_entry():
    @_with_auth
    def _handler(user, password):
        try:
            data = get_request_data_func()
            payload = parse_stream_cell(data)
            _, generator = cell_stream_service.stream_round_cell(
                user=user,
                round_id=payload['round_id'],
                child_id=payload['child_id'],
                system_prompt_id=payload['system_prompt_id'],
                max_response_tokens=payload['max_response_tokens'],
                request_id=payload['request_id'],
            )
            return Response(
                generator(),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no',
                    'Connection': 'close',
                }
            )
        except DTOError as e:
            return Response(
                f"data: {{\"done\": true, \"error\": {{\"msg\": \"{str(e)}\"}}}}\n\n",
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no',
                    'Connection': 'close',
                }
            )
        except cell_stream_service.CellStreamError as e:
            return Response(
                f"data: {{\"done\": true, \"error\": {{\"msg\": \"{str(e)}\"}}}}\n\n",
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no',
                    'Connection': 'close',
                }
            )
        except Exception as e:
            return Response(
                f"data: {{\"done\": true, \"error\": {{\"msg\": \"stream cell failed: {str(e)}\"}}}}\n\n",
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'X-Accel-Buffering': 'no',
                    'Connection': 'close',
                }
            )

    return _handler()


@conversation_v2_bp.route('/never_guess_my_usage/conversation/cell/stream_cancel', methods=['POST'])
def cell_stream_cancel_entry():
    @_with_auth
    def _handler(user, password):
        try:
            data = get_request_data_func()
            request_id = (data.get('request_id') or '').strip()
            if not request_id:
                return _resp_fail('missing request_id')
            cancelled = cell_stream_service.cancel_stream_cell(request_id)
            return _resp_ok({'request_id': request_id, 'cancelled': cancelled})
        except Exception as e:
            return _resp_fail(f'cancel stream cell failed: {str(e)}')

    return _handler()


@conversation_v2_bp.route('/never_guess_my_usage/conversation/cell/retry', methods=['POST'])
def cell_retry_entry():
    @_with_auth
    def _handler(user, password):
        try:
            data = get_request_data_func()
            payload = parse_retry_cell(data)
            result = retry_service.retry_cell_once(
                user=user,
                round_id=payload['round_id'],
                child_id=payload['child_id'],
                system_prompt_id=payload['system_prompt_id'],
                max_response_tokens=payload['max_response_tokens'],
            )
            return _resp_ok(result)
        except DTOError as e:
            return _resp_fail(str(e))
        except retry_service.RetryError as e:
            return _resp_fail(str(e))
        except Exception as e:
            return _resp_fail(f'retry cell failed: {str(e)}')

    return _handler()


@conversation_v2_bp.route('/never_guess_my_usage/conversation/legacy/migrate', methods=['POST'])
def legacy_migrate_entry():
    @_with_auth
    def _handler(user, password):
        try:
            data = get_request_data_func()
            payload = parse_legacy_migrate(data)
            result = legacy_migration_service.migrate_dialogs(
                user=user,
                dialog_ids=payload['dialog_ids'],
                target_models=payload['target_models'],
            )
            return _resp_ok(result)
        except DTOError as e:
            return _resp_fail(str(e))
        except legacy_migration_service.LegacyMigrationError as e:
            return _resp_fail(str(e))
        except Exception as e:
            return _resp_fail(f'legacy migrate failed: {str(e)}')

    return _handler()
