const ImportPromptButton = {
    template: `
<button
    data-toggle="modal"
    data-target="#ImportPromptModal"
    class="btn btn-secondary btn-sm btn-icon__sm mr-2"
>
    <i class="fa fa-file-import"></i>
</button>
    `
}

const ImportPromptModal = {

    data() {
        return {
            name: '',
            integration_uid: null,
            prompt_json: null,
            integrations: [],
            modal_style: {},
            fileName: '',
            error: null,
            is_loading: false,
        }
    },
    mounted() {
        $(this.$el).on('show.bs.modal', async () => {
            if (this.integrations.length === 0) {
                const api_url = this.$root.build_api_url('integrations', 'integrations', {
                    trailing_slash: true
                })
                const params = new URLSearchParams({section: 'ai'})
                const url = api_url + this.$root.project_id + '?' + params.toString()
                const resp = await fetch(url)
                if (!resp.ok) {
                    showNotify('ERROR', 'Error fetching integrations')
                } else {
                    this.integrations = await resp.json();
                    this.$nextTick(() => {
                        $('#selectorImportIntegration').selectpicker('refresh');
                    })
                }
            }
        })
        $(this.$el).on('hide.bs.modal', () => {
            this.name = ''
            this.fileName = ''
            this.prompt_json = null
            this.error = null
            this.$refs.import_file_input.value = null
        })
    },
    computed: {
        formatted_json() {
            this.error = null
            try {
                return this.prompt_json ?
                    JSON.stringify(JSON.parse(this.prompt_json), null, 5)
                    :
                    ''
            } catch (e) {
                this.error = 'Invalid json format'
            }
            return this.prompt_json
        },
        grouped_integrations() {
            return this.integrations.reduce((accum, item) => {
                accum[item.name] = accum[item.name] || []
                accum[item.name].push(item)
                return accum
            }, {})
        }
    },

    methods: {
        handleFileUpload(file) {
            let reader = new FileReader()
            reader.onload = (e) => {
                try {
                    const parsed = JSON.parse(e.target.result)
                    this.fileName = file.name
                    this.name = parsed.name
                    delete parsed.name
                    this.prompt_json = JSON.stringify(parsed)
                } catch (e) {
                    console.error(e)
                    this.error = e
                    throw e
                }
            }
            reader.onerror = (e) => {
                this.error = 'error reading file'
                this.prompt_json = null
                this.fileName = ''
            }
            this.error = null
            reader.readAsText(file)

        },
        handleDrop(e) {
            const file = e.dataTransfer.files[0]
            file && this.handleFileUpload(file)
        },
        handleInputFile(event) {
            const input = event.target
            if (input.files && input.files[0]) {
                this.handleFileUpload(input.files[0])
            }
        },
        async handleImport() {
            this.is_loading = true
            const api_url = this.$root.build_api_url('prompts', 'export_import', {
                trailing_slash: true
            }) + this.$root.project_id
            const data = {
                ...JSON.parse(this.prompt_json),
                name: this.name,
                integration_uid: this.integration_uid
            }
            const resp = await fetch(api_url, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            })
            if (!resp.ok) {
                showNotify('ERROR', 'Import Error')
                const errors = await resp.json()
                this.handleErrors(errors)
            } else {
                showNotify('SUCCESS', 'Prompt imported')
                this.$root.registered_components?.prompts?.refreshPromptsListTable()
                $(this.$el).modal('hide')
            }
            this.is_loading = false

        },
        handleErrors(errors) {
            console.error(errors)
            const {error} = errors
            this.error = error
        }
    },


    template: `
<div id="ImportPromptModal" class="modal" tabindex="-1"
    @dragover.prevent="modal_style = {'border': '2px dashed var(--basic)'}"
    @drop.prevent="modal_style = {'border': ''}"
>
    <div class="modal-dialog modal-dialog-centered"
         style="min-width: 1000px;"
    >
        <div class="modal-content p-0 flex-column"
            :style="modal_style"
        >
            <div class="w-100 d-flex flex-column px-4 pt-4">

                <div class="notification notification-error" style="flex-direction: row"
                    v-if="error"
                >
                    <div class="notification-body">
                        <div class="notification-content">
                            <div class="notification-title">{{ error }}</div>
                        </div>
                    </div>
                </div>

                <div class="d-flex gap-3">
                    <div class="w-1/2">
                        <p class="font-h5 font-semibold">Name</p>
                        <div class="custom-input mb-3 mt-2">
                            <input
                                type="text"
                                placeholder="Prompt name"
                                v-model="name"
                            />
                        </div>
                    </div>
                    <div class="w-1/2">
                        <p class="font-h5 font-semibold">Integration</p>
                        <select id="selectorImportIntegration"
                            class="selectpicker bootstrap-select__b mt-2 w-100-imp"
                            v-model="integration_uid"
                            data-style="btn">
                            <option :value="null">
                                Nothing selected
                            </option>
                            <optgroup
                                v-for="[g, gis] in Object.entries(grouped_integrations)"
                                :label="g"
                            >
                                <option
                                    v-for="i in gis"
                                    :value="i.uid"
                                >
                                    {{ i.config?.name }}
                                </option>
                            </optgroup>
                        </select>
                    </div>
                </div>

                <div class="form-group">
                    <div class="drop-area">
                        <label class="mb-0 d-flex align-items-center justify-content-center">
                            <input type="file" accept="application/JSON"
                                class="form-control form-control-alternative"
                               style="display: none"
                               @change="handleInputFile"
                               ref="import_file_input"
                            >
                            Drag & drop file or <span>&nbsp;browse</span>
                        </label>
                    </div>
                    <div class="preview-area"
                        v-if="fileName"
                    >
                        <div class="preview-area_item">
                            <span>{{ fileName }}</span>
                        </div>
                    </div>
                    <textarea class="form-control" rows="20"
                        :value="formatted_json"
                        @change="prompt_json = $event.target.value"
                        @drop.prevent="handleDrop"
                    ></textarea>

                </div>

            </div>
            <div class="d-flex justify-content-end px-4 pb-4">
                <button type="button" class="btn btn-secondary mr-2" data-dismiss="modal">
                    Close
                </button>
                <button type="button" class="btn btn-basic"
                    @click="handleImport"
                    :disabled="is_loading"
                >
                    Import <i v-if="is_loading" class="preview-loader__white ml-2"></i>
                </button>
            </div>
        </div>
    </div>
</div>
    `
}


register_component('ImportPromptButton', ImportPromptButton)
register_component('ImportPromptModal', ImportPromptModal)
