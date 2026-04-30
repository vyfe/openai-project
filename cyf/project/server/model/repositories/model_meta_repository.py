from peewee import DoesNotExist

from model.entities import ModelMeta, SystemPrompt


def get_model_meta_list(model_names: list = None, recommend: bool = None, status_valid: bool = None):
    query = ModelMeta.select()
    if model_names is not None:
        query = query.where(ModelMeta.model_name.in_(model_names))
    if recommend is not None:
        query = query.where(ModelMeta.recommend == recommend)
    if status_valid is not None:
        query = query.where(ModelMeta.status_valid == status_valid)
    return [model for model in query.dicts().iterator()] if query.exists() else []


def get_system_prompt_list(status_valid: bool = None):
    query = SystemPrompt.select()
    if status_valid is not None:
        query = query.where(SystemPrompt.status_valid == status_valid)
    return [prompt for prompt in query.dicts().iterator()] if query.exists() else []


def get_system_prompts_by_group():
    query = SystemPrompt.select().where(SystemPrompt.status_valid == True)
    grouped_prompts = {}
    for prompt in query.dicts().iterator():
        group = prompt["role_group"]
        grouped_prompts.setdefault(group, []).append(
            {
                "id": prompt["id"],
                "role_name": prompt["role_name"],
                "role_desc": prompt["role_desc"],
            }
        )
    return grouped_prompts


def get_system_prompt_by_id(prompt_id: int) -> dict:
    try:
        prompt = SystemPrompt.get_by_id(prompt_id)
        if not prompt or not prompt.status_valid:
            return None
        return {
            "id": prompt.id,
            "role_name": prompt.role_name,
            "role_desc": prompt.role_desc,
            "role_content": prompt.role_content,
        }
    except DoesNotExist:
        return None
