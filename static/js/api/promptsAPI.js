const ApiFetchPrompts = async () => {
    const api_url = V.build_api_url('prompts', 'prompts')
    const res = await fetch(`${api_url}/${getSelectedProjectId()}`, {
        method: 'GET',
    })
    return res.json();
}

const ApiFetchPromptById = async (promptId) => {
    const api_url = V.build_api_url('prompts', 'prompt')
    const res = await fetch(`${api_url}/${getSelectedProjectId()}/${promptId}`, {
        method: 'GET',
    })
    return res.json();
}

const ApiCreatePrompt = async (promptName, type) => {
    const api_url = V.build_api_url('prompts', 'prompts')
    const res = await fetch(`${api_url}/${getSelectedProjectId()}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            "name": promptName,
            "type": type,
            "prompt": "",
        })
    })
    return res.json();
}

const ApiUpdatePrompt = async (prompt) => {
    const api_url = V.build_api_url('prompts', 'prompt')
    let embeddings;
    if (typeof prompt.embeddings === 'string') {
        embeddings = prompt.embeddings;
    } else if (prompt.embeddings?.id) {
        embeddings = prompt.embeddings.id
    } else {
        embeddings = '0'
    }
    const res = await fetch(`${api_url}/${getSelectedProjectId()}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            "id": prompt.id,
            "name": prompt.name,
            "type": prompt.type,
            "prompt": prompt.prompt,
            "description": prompt.description,
            "tags": prompt.tags,
            "embedding": embeddings,
            "is_active_input": prompt.is_active_input,
        })
    })
    return res.json();
}

const ApiUpdateExampleField = async (promptId, exampleId, input, output, isActive) => {
    const api_url = V.build_api_url('prompts', 'example')

    const res = await fetch(`${api_url}/${getSelectedProjectId()}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            "prompt_id": promptId,
            "id": exampleId,
            "input": input,
            "output": output,
            "is_active": isActive,
        })
    })
    return res.json();
}

const ApiUpdateVariableField = async (promptId, varId, name, value) => {
    const api_url = V.build_api_url('prompts', 'variable')

    const res = await fetch(`${api_url}/${getSelectedProjectId()}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            "prompt_id": promptId,
            "id": varId,
            "name": name,
            "value": value,
        })
    })

    if (!res.ok) {
        const error = await res.json();
        const msg = "Error occurred while variable update\n" + error?.map(i => i?.msg || '').join('\n')
        throw Error(msg)
    }

    return res.json();
}

const ApiCreateExample = async (promptId, input, output) => {
    const api_url = V.build_api_url('prompts', 'example')
    const res = await fetch(`${api_url}/${getSelectedProjectId()}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            "prompt_id": promptId,
            "input": input,
            "output": output,
        })
    })
    return res.json();
}

const ApiCreateVariable = async (promptId, name, value) => {
    const api_url = V.build_api_url('prompts', 'variable')
    const res = await fetch(`${api_url}/${getSelectedProjectId()}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            "prompt_id": promptId,
            "name": name,
            "value": value,
        })
    })
    if (!res.ok) {
        const error = await res.json();
        const msg = "Error occurred\n" + error?.map(i => i?.msg || '').join('\n')
        showNotify('ERROR', msg)
        throw Error(msg)
    }
    return res.json();
}

const ApiRunTest = async (prompt, input = null, integrationUid, embedding_settings = null) => {
    const api_url = V.build_api_url('prompts', 'predict')
    const params = {
        "prompt_id": prompt.id,
        "integration_uid": integrationUid,
        "integration_settings": prompt.integration_settings,
        update_prompt: true
    }
    if (embedding_settings) {
        params["embedding_settings"] = embedding_settings;
    }
    if (input) params["input"] = input;
    const res = await fetch(`${api_url}/${getSelectedProjectId()}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(params)
    })

    if (!res.ok) {
        const errorMsg = await res.text();
        throw Error(errorMsg)
    }

    return res.json();
}

const ApiRunChat = async (prompt, input = null, chat_history, integrationUid, embedding_settings = null) => {
    const api_url = V.build_api_url('prompts', 'predict')
    const params = {
        "prompt_id": prompt.id,
        "integration_uid": integrationUid,
        "integration_settings": prompt.integration_settings,
        "update_prompt": true,
        "input": input,
        "chat_history": chat_history,
    }
    if (embedding_settings) {
        params["embedding_settings"] = embedding_settings;
    }

    const res = await fetch(`${api_url}/${getSelectedProjectId()}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(params)
    })

    return res.json();
}

const ApiDeletePrompt = async (promptId) => {
    const api_url = V.build_api_url('prompts', 'prompt')
    const res = await fetch(`${api_url}/${getSelectedProjectId()}/${promptId}`, {
        method: 'DELETE',
    })
}

const ApiDeleteExample = async (exampleId) => {
    const api_url = V.build_api_url('prompts', 'example')
    const res = await fetch(`${api_url}/${getSelectedProjectId()}/${exampleId}`, {
        method: 'DELETE',
    })
}

const ApiDeleteVariable = async (variableId) => {
    const api_url = V.build_api_url('prompts', 'variable')
    const res = await fetch(`${api_url}/${getSelectedProjectId()}/${variableId}`, {
        method: 'DELETE',
    })
}

const fetchTagsAPI = async () => {
    const api_url = V.build_api_url('prompts', 'tags')
    const res = await fetch(`${api_url}/${getSelectedProjectId()}`, {
        method: 'GET',
    })
    return res.json();
}
const fetchPromptTagsAPI = async (promptId) => {
    const api_url = V.build_api_url('prompts', 'tags')
    const res = await fetch(`${api_url}/${getSelectedProjectId()}/${promptId}`, {
        method: 'GET',
    })
    return res.json();
}

const updatePromptTagsAPI = async (tags, promptId) => {
    const api_url = V.build_api_url('prompts', 'tags')
    const res = await fetch(`${api_url}/${getSelectedProjectId()}/${promptId}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(tags)

    })
    return res.json();
}

const updatePromptNameAPI = async (promptId, promptName) => {
    const api_url = V.build_api_url('prompts', 'prompt')
    const res = await fetch(`${api_url}/${getSelectedProjectId()}/${promptId}`, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            "name": promptName
        })
    })
    return res.json();
}

const fetchPromptVersionsAPI = async (promptName) => {
    const api_url = V.build_api_url('prompts', 'versions')
    const res = await fetch(`${api_url}/${getSelectedProjectId()}/${promptName}`, {
        method: 'GET',
    })
    return res.json();
}

const fetchPromptEmbeddingsAPI = async () => {
    const api_url = V.build_api_url('embeddings', 'embedding')
    const res = await fetch(`${api_url}/${getSelectedProjectId()}`, {
        method: 'GET',
    })
    return res.json();
}

const ApiCreatePromptVersion = async (promptId, versionName) => {
    const api_url = V.build_api_url('prompts', 'versions')
    const res = await fetch(`${api_url}/${getSelectedProjectId()}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            "prompt_id": promptId,
            "version": versionName,
        })
    })
    return res.json();
}
