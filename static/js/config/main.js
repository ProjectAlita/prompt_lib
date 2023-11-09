const regenerateToken = async (row_key='token', field='value') => {
    const api_url = V.build_api_url('prompts', 'config', {trailing_slash: true})
    const resp = await fetch(api_url + V.project_id, {
        method: 'PUT',
    })
    if (resp.ok) {
        const {token} = await resp.json()
        V.registered_components.table_config.table_action('updateCellByUniqueId', {
            id: row_key,
            field: field,
            value: token,
            reinit: true
        })
        showNotify('SUCCESS', 'Token refreshed')
    } else {
        showNotify('ERROR', 'Token refresh error')
    }
}

const handleIntegrationChange = (newValue, row_key='integration_uid', field='value') => {
    V.registered_components.table_config.table_action('updateCellByUniqueId', {
        id: row_key,
        field: field,
        value: newValue,
        reinit: true,
    })
}

const valueFormatters = {
    token: (value, row, index, field) => value?.token
}

const getExpirationData = (expires) => {
    if (expires === undefined || expires === null) {
        return {text: '', color: 'inherit'}
    }
    const expDate = new Date(expires + 'Z')
    const millisecondsPerDay = 24 * 60 * 60 * 1000
    const dateDiff = expDate - new Date()
    const daysLeft = Math.round(dateDiff / millisecondsPerDay)
    switch (true) {
        case daysLeft < 0 || Object.is(daysLeft, -0):
            return {text: 'Expired', color: 'var(--red)'}
        case daysLeft === 0:
            return {text: 'Expires today', color: 'var(--red)'}
        case daysLeft === 1:
            return {text: 'Expires in: 1 day', color: 'var(--warn)'}
        case daysLeft <= 7:
            return {text: `Expires in: ${daysLeft} days`, color: 'var(--yellow)'}
        default:
            return {text: `Expires in: ${daysLeft} days`, color: 'var(--success)'}
    }
}

const actionFormatters = {
    integration_uid: (value, row, index, field) => {
        const processIntegrations = integrations => {
            return integrations.map(({uid, config}) => {
                return `
                    <option
                        value="${uid}"
                        ${uid === row.value && 'selected'}
                    >
                        ${config.name}
                    </option>
                `
            })
        }
        const processGroup = (name, integrations) => {
            return `
                <optgroup label="${name}"></optgroup>
                ${processIntegrations(integrations)}
            `
        }

        return `
            <select class="custom-select"
                onchange="handleIntegrationChange(this.value)"
            >
                ${Object.entries(value).map(
                    ([group, integrations]) => processGroup(group, integrations)
                )}
            </select>
        `
    },
    token: (value, row, index, field) => {
        const {expires} = row.value
        const {text: expireText, color: expColor} = getExpirationData(expires)
        return `
                <button type="button" 
                    class="btn btn-secondary btn-icon btn-icon__purple ${(expires === null || expires === undefined)&& 'hidden'}"
                    onclick="copyTokenToClip(this)"
                >
                    <i class="icon__18x18 icon-copy"></i>
                </button>
                <button class="btn btn-secondary" onclick="regenerateToken()">
                    ${expires === null || expires === undefined ? 'Generate' : 'Regenerate'} token
                </button>
                <p class="m-0 font-h6" style="color: ${expColor}">${expireText}</p>
        `
    }
}

var valueFormatter = (value, row, index, field) => {
    const formatterFunc = valueFormatters[row.key]
    return formatterFunc === undefined ? value : formatterFunc(value, row, index, field)
}

var actionFormatter = (value, row, index, field) => {
    const formatterFunc = actionFormatters[row.key]
    return formatterFunc === undefined ? value : formatterFunc(value, row, index, field)
}

var tokenCellStyle = (value, row, index, field) => {
    return {
        css: {
            "max-width": "500px",
            "text-wrap": "wrap",
        }
    }
}


var downloadArtifactFormatter = (value, row, index) => {
    const artifact_download_url = V.build_api_url(
        'prompts',
        'config_bucket',
        {trailing_slash: true}
    )
    const file_name = encodeURIComponent(row['name'])
    return `
        <a 
            href="${artifact_download_url}${V.project_id}/${file_name}" 
            class="fa fa-download btn-action" 
            download="${row['name']}"
        ></a>
    `
}

const doCopy = () => {
    try {
        const copySuccess = document.execCommand('copy')
        copySuccess ?
            showNotify('SUCCESS', 'Copied to clipboard')
            :
            showNotify('ERROR', 'Error copying to clipboard')
    } catch (err) {
        showNotify('ERROR', 'Error copying to clipboard')
    }
}

const copyToClip = data => {
    const textArea = document.createElement('textarea')
    // Avoid scrolling to bottom
    textArea.style.top = '0'
    textArea.style.left = '0'
    textArea.style.position = 'fixed'
    textArea.value = data

    document.body.appendChild(textArea)
    textArea.focus()
    textArea.select()
    doCopy()
    document.body.removeChild(textArea)
}

const copyConfigToClip = () => {
    const data = V.registered_components.table_config.table_action('getData').reduce((accum, item) => {
        accum[item.key] = item.key === 'token' ? item.value.token : item.value
        return accum
    }, {})
    copyToClip(JSON.stringify(data, null, 2))
}

const copyTokenToClip = (el) => {
    copyToClip($(el).closest('tr').find('td:nth-child(2)').text())
}
