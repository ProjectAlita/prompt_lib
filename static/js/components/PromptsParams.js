const PromptsParams = {
    props: {
        selectedPrompt: {
            type: Object,
            default: {
                "id": null,
                "name": "",
                "prompt": "",
                "examples": [],
                "variables": [],
            }
        },
        integrations: {
            type: Array,
            default: [],
        },
        tags: [],
        isPromptLoading: false,
    },
    components: {
        PromptFreeform,
        PromptChat,
        PromptsVertexIntegration,
        PromptsOpenaiIntegration,
        PromptsAzureOpenaiIntegration,
        PromptsAiDialIntegration,
        PromptsTagsModal,
        PromptsEditorName,
        PromptsEditorField,
        PromptsRange,
    },
    data() {
        return {
            editablePrompt: {
                name: "",
                prompt: "",
                examples: [],
                model_settings: {},
                embeddings: null,
            },
            testInput: '',
            testOutput: [{
                type: 'text',
                content: '',
            }],
            isRunClicked: false,
            selectedIntegration: {},
            filteredModels: [],
            selectedComponentInt: "",
            isRunLoading: false,
            isContextLoading: false,
            promptTags: [],
            promptEmbeddings: [],
            showTagsModal: false,
            promptVersions: [],
            selectedPromptVersion: {
                id: null,
                version: 'latest',
            },
            newDescription: '',
            isVersionLoaded: false,
            windowHeight: window.innerHeight,
            isShowEmbedding: false,
            embedding_settings: {
                "top_k": 20,
                "cutoff": 0.1
            },
            isShowContext: false,
        }
    },
    computed: {
        isInvalidContext() {
            if (this.isShowContext) {
                return this.isRunClicked && !this.editablePrompt.prompt
            } else {
                return false
            }
        },
        isLatestVersion() {
            return this.selectedPrompt.version === 'latest';
        },
        isDisableAddButton() {
            return !this.testOutput[0].content || !this.testInput ||
                this.testOutput[0].type === 'image' || this.testOutput.length > 1;
        },
        responsiveBarHeight() {
            return `${(this.windowHeight - 95)}px`;
        },
        responsiveContentHeight() {
            return `${(this.windowHeight - 155)}px`;
        },
        responsiveMainContainerHeight() {
            return `${(this.windowHeight - 207)}px`;
        }
    },
    watch: {
        promptEmbeddings(newVal, oldVal) {
            this.$nextTick(() => {
                 $('.selectpicker').selectpicker('render').selectpicker('refresh');
            })
        },
        selectedPrompt: {
            handler: function (newVal, oldVal) {
                if (newVal.id === this.editablePrompt.id) return;
                this.editablePrompt = _.cloneDeep(newVal);
                if (newVal.integration_uid) {
                    this.integrations.forEach(integration => {
                        if (integration.uid === newVal.integration_uid) {
                            this.selectedIntegration = integration;
                            this.selectedComponentInt = integration.name;
                            this.changeIntegration(integration);
                            $("#selectIntegration").val(integration.config.name);
                        }
                    })
                } else {
                    this.selectedComponentInt = "";
                    this.selectedIntegration = "";
                }
                if (newVal.prompt) {
                    this.isShowContext = true;
                } else {
                    this.isShowContext = false;
                }
                this.testInput = newVal.test_input ? newVal.test_input : "";
                this.testOutput = [{
                    type: 'text',
                    content: '',
                }];
                this.isRunClicked = false;
                this.fetchPromptTags(this.selectedPrompt.id);
                if (newVal.embeddings?.id) {
                    this.editablePrompt.embeddings = newVal["embeddings"];
                }
                else {
                    this.editablePrompt.embeddings = {};
                }
                this.fetchPromptEmbeddings(newVal.embeddings);
                this.fetchPromptVersions(newVal.name);
                this.$nextTick(() => {
                    $("#selectIntegration").selectpicker('refresh');
                    $('#promptsParamsTable').bootstrapTable('load', this.editablePrompt.examples);
                    $('#variablesTable').bootstrapTable('load', this.editablePrompt.variables);
                })
            },
            deep: true
        },
        selectedIntegration: {
            handler: function (newVal, oldVal) {
                if (!newVal) return
                this.changeIntegration(newVal)
            },
            deep: true
        },
    },
    mounted() {
        $('#promptsParamsTable').bootstrapTable();
        $('#variablesTable').bootstrapTable();
        this.$nextTick(() => {
            window.addEventListener('resize', this.onResize);
        })
    },
    beforeDestroy() {
        window.removeEventListener('resize', this.onResize);
    },
    methods: {
        onResize() {
            this.windowHeight = window.innerHeight
        },
        selectPromptVersion({ target: { value }}) {
            this.selectedPromptVersion = this.promptVersions.find(v => v.id === +value);
        },
        fetchPromptTags(promptId) {
            fetchPromptTagsAPI(promptId).then((tags) => {
                this.promptTags = tags;
            })
        },
        fetchPromptVersions(promptName) {
            fetchPromptVersionsAPI(promptName).then((prompts) => {
                this.promptVersions = prompts.map(({ id, version }) => ({ id, version }));
                this.selectedPromptVersion = this.promptVersions.find(v => v.id === this.selectedPrompt.id);
            }).finally(() => {
                this.isVersionLoaded = true;
                this.$nextTick(() => {
                    if (this.selectedPromptVersion) {
                        $('#selectedPromptVersion').val(this.selectedPromptVersion.id);
                        $('#selectedPromptVersion').selectpicker('refresh');
                    }
                })
            })
        },
        changeIntegration(newVal) {
            this.filteredModels = this.filterModelsByType(newVal.settings.models, this.editablePrompt);
            if (this.selectedPrompt.integration_uid) {
                const existedInt = this.integrations
                    .find(integration => integration.uid === newVal.uid)
                this.selectedComponentInt = newVal.name;
                if (existedInt.uid === this.selectedPrompt.integration_uid) {
                    this.editablePrompt.model_settings = { ...this.selectedPrompt.model_settings }
                    return;
                }
            }
            this.editablePrompt.model_settings = this.integrations
                .find(integration => integration.uid === newVal.uid).settings;
            this.selectedComponentInt = newVal.name;
        },
        fetchPromptEmbeddings(promptEmbedding) {
            fetchPromptEmbeddingsAPI().then((embeddings) => {
                this.promptEmbeddings = embeddings.map(({ id, library_name }) => ({ id, library_name }));
                this.promptEmbeddings = [{id: 0, library_name: "Without embeddings"}].concat(this.promptEmbeddings);
                if (promptEmbedding?.id) {
                    this.$nextTick(() => {
                        this.isShowEmbedding = true;
                        $('#selectedPromptEmbedding').val(promptEmbedding.id);
                        $('#selectedPromptEmbedding').selectpicker('refresh');
                    })
                } else {
                    this.isShowEmbedding = false;
                }
            })
        },
        handle_advanced_settings_icon(e) {
            this.advanced_settings_icon = this.$refs.advanced_settings.classList.contains('show') ?
                'icon__16x16 icon-arrow-up__16 rotate-90' : 'icon__16x16 icon-arrow-down__16'
        },
        filterModelsByType(models, prompt) {
            try {
                if (prompt.type === 'freeform') {
                    return models.filter(model =>
                        model.capabilities.completion === true ||
                        model.capabilities.chat_completion === true
                    )
                }
                if (prompt.type === 'chat') {
                    return models.filter(model =>
                        model.capabilities.chat_completion === true
                    )
                }
            } catch (e) {
                return models;
            }
        },
        addEmptyParamsRow()  {
            $('#promptsParamsTable').bootstrapTable(
                'append',
                {id: Date.now() + Math.floor(Math.random() * 1000),"input": "", "output": "", "action": ""}
            )
        },
        addEmptyVariableRow(){
            $('#variablesTable').bootstrapTable(
                'append',
                {id: Date.now() + Math.floor(Math.random() * 1000),"name": "", "value": "", "action": ""}
            )
        },
        checkFields(rowId) {
            const row = $('#promptsParamsTable').bootstrapTable('getRowByUniqueId', rowId)
            if (row.input && row.output) {
                $(`#promptsParamsTable tr[data-uniqueid=${rowId}]`).find('textarea').each(function () {
                    $(this).attr('disabled', 'disabled');
                })
                ApiCreateExample(this.editablePrompt.id, row.input, row.output).then(newRow => {
                    $('#promptsParamsTable')
                        .bootstrapTable('removeByUniqueId', rowId)
                        .bootstrapTable('append', newRow );
                    showNotify('SUCCESS', `Input/Output saved.`);
                })
            }
        },
        checkVariableFields(rowId) {
            const row = $('#variablesTable').bootstrapTable('getRowByUniqueId', rowId)
            if (row.name && row.value) {
                $(`#variablesTable tr[data-uniqueid=${rowId}]`).find('textarea').each(function () {
                    $(this).attr('disabled', 'disabled');
                })
                ApiCreateVariable(this.editablePrompt.id, row.name, row.value).then(newRow => {
                    $('#variablesTable')
                        .bootstrapTable('removeByUniqueId', rowId)
                        .bootstrapTable('append', newRow);
                    showNotify('SUCCESS', `Variable saved.`);
                })
            }
        },
        updateField(rowId, isChecked = null) {
            const row = $('#promptsParamsTable').bootstrapTable('getRowByUniqueId', rowId);
            ApiUpdateExampleField(this.editablePrompt.id, rowId, row.input, row.output, isChecked ?? row.is_active).then(data => {
                if (this.isLatestVersion) {
                    $(`#promptsParamsTable tr[data-uniqueid=${rowId}]`).find('textarea').each(function () {
                        $(this).removeAttr("disabled");
                    })
                }
                showNotify('INFO', `Input/Output updated.`);
            })
        },
        updateVariableField(rowId) {
            const row = $('#variablesTable').bootstrapTable('getRowByUniqueId', rowId)
            ApiUpdateVariableField(this.editablePrompt.id, rowId, row.name, row.value).then(data => {
                $(`#variablesTable tr[data-uniqueid=${rowId}]`).find('textarea').each(function () {
                    $(this).removeAttr("disabled");
                })
                showNotify('INFO', `Variable updated.`);
            })
            .catch(err => {
                $(`#variablesTable tr[data-uniqueid=${rowId}]`).find('textarea').each(function () {
                    $(this).removeAttr("disabled");
                })
                showNotify("ERROR", err)
            })
        },
        runTest() {
            this.isRunClicked = true;
            if (this.isShowContext && !this.editablePrompt.prompt) return
            const integrationId = this.integrations.find(integration => integration.uid === this.selectedIntegration.uid)
            const computedCondition = this.editablePrompt.is_active_input
                ? this.testInput && this.selectedIntegration
                : this.selectedIntegration;
            if (computedCondition) {
                this.isRunLoading = true;
                const computedInput = this.editablePrompt.is_active_input ? this.testInput : null;
                const embeddingSetting = !!this.editablePrompt.embeddings?.id && this.isShowEmbedding
                    ? this.embedding_settings
                    : null;
                ApiRunTest(this.editablePrompt, computedInput, integrationId.uid, embeddingSetting).then(data => {
                    this.testOutput = data.messages;
                    this.testOutput.map(msg => {
                        if (msg.type === 'image') {
                            msg.content = `data:${msg.content.type};base64, ${msg.content.data}`;
                        }
                    })
                }).catch(err => {
                    showNotify('ERROR', err)
                }).finally(() => {
                    this.isRunLoading = false;
                    this.isRunClicked = false;
                })
            }
        },
        updatePrompt(e) {
            this.editablePrompt.prompt = e.target.value;
            this.isContextLoading = true;
            this.editablePrompt.embeddings = $('#selectedPromptEmbedding').find(":selected").val();
            ApiUpdatePrompt(this.editablePrompt).then(data => {
                this.isContextLoading = false;
                showNotify('SUCCESS', `Context updated.`)
            });
        },
        updateEmbeddings(e) {
            this.editablePrompt.embeddings = $('#selectedPromptEmbedding').find(":selected").val();
            ApiUpdatePrompt(this.editablePrompt).then(data => {
                this.isContextLoading = false;
                showNotify('SUCCESS', `Embedding updated.`)
            });
        },
        saveSettings() {
            ApiUpdatePrompt(this.editablePrompt).then(data => {
                showNotify('SUCCESS', `Settings updated.`)
            });
        },
        updateSetting(settings) {
            const settingsKeys = ['temperature', 'top_k', 'top_p', 'model_name', 'max_decode_steps', 'max_tokens'];
            const selectedSetting = {};
            for (const setting in settings) {
                if (settingsKeys.includes(setting)) {
                    selectedSetting[setting] = settings[setting];
                }
            }
            this.editablePrompt.integration_settings = Object.assign({}, selectedSetting);
        },
        addTestResult() {
            const rowId = Date.now() + Math.floor(Math.random() * 1000)
            $('#promptsParamsTable').bootstrapTable(
                'append',
                {
                    id: rowId,
                    "input": this.testInput,
                    "output": this.testOutput[0].content,
                    "action": ""
                }
            )
            this.checkFields(rowId);
        },
        showError(value) {
            return this.isRunClicked ? value : true;
        },
        hasError(value) {
            return value.length > 0;
        },
        deleteExample(exampleId) {
            ApiDeleteExample(exampleId).then(() => {
                showNotify('SUCCESS', 'Example delete.');
            });
        },
        deleteVariable(varId) {
            ApiDeleteVariable(varId).then(() => {
                showNotify('SUCCESS', 'Variable delete.');
            });
        },
        updateTags(tags) {
            this.editablePrompt.tags = tags;
        },
        LoadVersion() {
            vueVm.registered_components['prompts'].FetchPromptById(this.selectedPromptVersion.id);
        },
        deleteVersion() {
            ApiDeletePrompt(this.selectedPromptVersion.id).then(data => {
                showNotify('SUCCESS', 'Version delete.');
                const latestVersionId = this.promptVersions.find(v => v.version === 'latest').id;
                vueVm.registered_components['prompts'].FetchPromptById(latestVersionId);
            });
        },
        updateCbxInput({ target: { checked }}) {
            this.editablePrompt.is_active_input = !checked;
            this.isRunClicked = false;
            const isActive = !checked ? 'enabled' : 'disabled';
            ApiUpdatePrompt(this.editablePrompt).then(data => {
                showNotify('INFO', `Input ${isActive}.`)
            });
        },
        changeTestInput({ target: { value }}) {
            this.testInput = value;
        },
        showEmbedding() {
            this.isShowEmbedding = !this.isShowEmbedding;
            if (!this.isShowEmbedding) {
                this.editablePrompt.embeddings = {};
                ApiUpdatePrompt(this.editablePrompt).then(data => {
                    showNotify('SUCCESS', `Embedding updated.`)
                });
            }
        },
        showContext() {
            this.isShowContext = !this.isShowContext;
            if (!this.isShowContext) {
                this.editablePrompt.prompt = ""
                ApiUpdatePrompt(this.editablePrompt).then(data => {
                    showNotify('SUCCESS', `Context updated.`)
                });
            }
        }
    },
    template: `
    <div class="d-flex">
        <div class="flex-grow-1 mr-3">
            <div class="card p-28">
                <div class="d-flex justify-content-between mb-2">
                    <promptsEditorName
                        v-show="!isPromptLoading"
                        :key="selectedPrompt.id"
                        :editable-prompt="editablePrompt"
                        v-model="editablePrompt.name">
                    </promptsEditorName>
                    <div class="d-flex">
                        <a class="btn btn-secondary mr-2"
                            download
                            :class="{'disabled': isPromptLoading}"
                            :href="
                                $root.build_api_url('prompts', 'export_import') +
                                '/' + $root.project_id +
                                '/' + editablePrompt.id +
                                '?as_file=true'"
                        >
                            Export
                        </a>
                        <button type="button" :disabled="isPromptLoading"
                            class="btn btn-secondary mr-2" @click="$emit('open-create-version-modal')">
                            Save version
                        </button>
                        <button type="button" :disabled="isRunLoading || isPromptLoading"
                            v-if="selectedPrompt.type === 'freeform'"
                            class="btn btn-basic d-flex align-items-center" @click="runTest">
                            Run
                            <i v-if="isRunLoading" class="preview-loader__white ml-2"></i>
                        </button>
                    </div>
                </div>
                <div class="container-scroll mt-3" :style="{'height': responsiveMainContainerHeight}">
                    <div class="position-relative" style="height: 164px" v-show="isPromptLoading">
                        <div class="layout-spinner">
                            <div class="spinner-centered">
                                <i class="spinner-loader__32x32"></i>
                            </div>
                        </div>
                    </div>
                    <div v-show="!isPromptLoading">
                        <promptsEditorField
                            title="Description"
                            :key="selectedPrompt.id"
                            :editable-prompt="editablePrompt"
                            v-model="editablePrompt.description">
                        </promptsEditorField>
                        <div>
                            <div class="d-flex justify-content-between">
                                <p class="font-h6 font-bold text-gray-800 flex-grow-1 mb-1" style="color: #32325D">CONTEXT</p>
                                <label class="custom-toggle" style="margin-top: 0">
                                    <input type="checkbox" 
                                    :checked="isShowContext"
                                    @click="showContext">
                                    <span class="custom-toggle_slider round"></span>
                                </label>
                            </div>
                            
                            <div class="w-100" v-if="isShowContext">
                                <div class="custom-input w-100 position-relative"
                                    :class="{ 'invalid-input': isInvalidContext }">
                                    <textarea
                                        :disabled="isContextLoading || !isLatestVersion"
                                        :value="editablePrompt.prompt"
                                        @change="updatePrompt"
                                        class="form-control password-mask" rows="5" id="SecretUpdateValue"></textarea>
                                        <div class="spinner__right-bottom" v-if="isContextLoading">
                                            <i class="spinner-loader__16x16"></i>
                                        </div>
                                </div>
                            </div>
                        </div>
                        <div class="mt-3 mb-4">
                            <div class="d-flex justify-content-between">
                                <p class="font-h6 font-bold text-gray-800 flex-grow-1 mb-1" style="color: #32325D">RETRIEVER</p>
                                <label class="custom-toggle" style="margin-top: 0">
                                    <input type="checkbox" 
                                    :checked="isShowEmbedding"
                                    @click="showEmbedding">
                                    <span class="custom-toggle_slider round"></span>
                                </label>
                            </div>
                            <div v-show="isShowEmbedding">
                                <select 
                                    id="selectedPromptEmbedding" class="selectpicker bootstrap-select__b bootstrap-select__b-sm w-100-imp displacement-ml-4"
                                    @change="updateEmbeddings" v-model="editablePrompt.embeddings" data-style="btn">
                                    <option v-for="embedding in promptEmbeddings" :value="embedding.id">{{ embedding.library_name }}</option>
                                </select>
                                <div class="d-flex justify-content-between gap-3 mt-4">
                                    <prompts-range
                                        @register="$root.register"
                                        instance_name="prompts-range"
                                        class="w-1/2"
                                        title="Top-K"
                                        :step="1"
                                        :minValue="0"
                                        :maxValue="20"
                                        v-model:modelValue="embedding_settings.top_k"
                                    ></prompts-range>
                                    <prompts-range
                                        @register="$root.register"
                                        instance_name="prompts-range"
                                        class="w-1/2"
                                        title="Cut-off score"
                                        :step="0.01"
                                        :minValue="0"
                                        :maxValue="1"
                                        v-model:modelValue="embedding_settings.cutoff"
                                    ></prompts-range>
                                </div>
                            </div>
                        </div>
                        <div class="mt-3">
                            <p class="font-h6 font-bold text-gray-800" style="color: #32325D">VARIABLES</p>
                            <table
                                id="variablesTable"
                                class="w-100 table-transparent mb-2 params-table"
                                data-toggle="table"
                                data-unique-id="id"
                            >
                                <thead class="thead-light">
                                    <tr>
                                        <th data-field="id" data-visible="false"></th>
                                        <th data-field="name"
                                            data-formatter="VariableTable.textareaFormatter"
                                        >
                                            <span class="font-h6 font-semibold text-gray-800">Name</span>
                                        </th>
                                        <th data-field="value"
                                            data-formatter="VariableTable.textareaFormatter"
                                        >
                                            <span class="font-h6 font-semibold text-gray-800">Value</span>
                                        </th>
                                        <th data-width="56" data-width-unit="px"
                                            data-field="action"
                                            data-formatter="VariableTable.deleteFormatter"
                                        ></th>
                                    </tr>
                                </thead>
                                <tbody style="border-bottom: solid 1px #EAEDEF">
                                </tbody>
                            </table>
                            <button type="button" class="btn btn-sm btn-secondary mt-2"
                                :disabled="!isLatestVersion"
                                @click="addEmptyVariableRow">
                                <i class="fas fa-plus mr-2"></i>Add Variable
                            </button>
                        </div>
                    </div>
                    <PromptFreeform
                        v-show="editablePrompt.type === 'freeform'"
                        :selectedPrompt="selectedPrompt"
                        :isLatestVersion="isLatestVersion"
                        :editablePrompt="editablePrompt"
                        :isPromptLoading="isPromptLoading"
                        :testOutput="testOutput"
                        :testInput="testInput"
                        :is-run-loading="isRunLoading"
                        :is-run-clicked="isRunClicked"
                        @run-test="runTest"
                        @add-test-result="addTestResult"
                        @change-test-input="changeTestInput"
                        @update-cbx-input="updateCbxInput">
                    </PromptFreeform>
                    <PromptChat
                        v-show="editablePrompt.type === 'chat'"
                        :selectedPrompt="selectedPrompt"
                        :isLatestVersion="isLatestVersion"
                        :editablePrompt="editablePrompt"
                        :isPromptLoading="isPromptLoading"
                        :integrations="integrations"
                        :selectedIntegration="selectedIntegration"
                        @run-chat="isRunClicked = true"
                        :isShowEmbedding="isShowEmbedding"
                        :embedding_settings="embedding_settings"
                        @update-cbx-input="updateCbxInput">
                    </PromptChat>
                </div>
            </div>
        </div>
        <div class="card p-4" style="min-width: 340px; width: 340px" :style="{'height': responsiveBarHeight}">
            <div class="d-flex justify-content-between">
                <p class="font-h4 font-bold mb-4">Settings</p>
            </div>
            <div class="position-relative h-100" v-if="isPromptLoading">
                <div class="layout-spinner">
                    <div class="spinner-centered">
                        <i class="spinner-loader__32x32"></i>
                    </div>
                </div>
            </div>
            <div v-show="!isPromptLoading" :style="{'height': responsiveContentHeight}" style="overflow-y: scroll;">
                <div class="select-validation" v-show="isVersionLoaded">
                    <p class="font-h5 font-semibold mb-1">Select version</p>
                    <select id="selectedPromptVersion" class="selectpicker bootstrap-select__b displacement-ml-4 bootstrap-select__b-sm"
                        @change="selectPromptVersion"
                        data-style="btn">
                        <option v-for="version in promptVersions" :value="version.id">{{ version.version }}</option>
                    </select>
                    <div class="d-flex justify-content-between">
                        <button type="button"
                            class="btn btn-basic d-flex align-items-center justify-content-center mt-1 flex-grow-1 mr-1" @click="LoadVersion">
                            Load version
                        </button>
                        <button type="button"
                            :disabled="selectedPromptVersion.version === 'latest'"
                            class="btn btn-secondary d-flex align-items-center mt-1" @click="deleteVersion">
                            Delete version
                        </button>
                    </div>
                </div>
                <div class="d-flex mt-4 flex-column">
                    <div>
                        <span class="font-h6 font-bold mr-2">TAGS:</span>
                        <button class="btn btn-xs btn-painted mr-1 rounded-pill mb-1" v-for="tag in editablePrompt.tags"
                            :style="{'--text-color': tag.color, '--brd-color': tag.color}">{{tag.tag}}
                        </button>
                    </div>
                    <div class="d-flex mt-1">
                        <button type="button" class="btn btn-default btn-xs btn-icon__xs mr-2"
                            @click="showTagsModal = true">
                            <i class="icon__18x18 icon-edit" data-toggle="tooltip" data-placement="top" title="Edit tags"></i>
                        </button>
                        <p class="font-h5">Edit tags</p>
                    </div>
                </div>
                <div class="select-validation mt-4" :class="{'invalid-select': !showError(selectedIntegration)}">
                    <p class="font-h5 font-semibold mb-1">Select integration</p>
                    <select id="selectIntegration" class="selectpicker bootstrap-select__b displacement-ml-4 bootstrap-select__b-sm"
                        v-model="selectedIntegration"
                        data-style="btn">
                        <option v-for="integration in integrations" :value="integration">{{ integration.config.name }}</option>
                    </select>
                    <span class="input_error-msg">Integration is require.</span>
                </div>
                <PromptsVertexIntegration
                    :is-run-clicked="isRunClicked"
                    :selected-prompt="editablePrompt"
                    :filtered-models="filteredModels"
                    @update-setting="updateSetting"
                    :key="selectedIntegration.uid + editablePrompt?.id"
                    v-if="selectedIntegration.name === 'vertex_ai'">
                </PromptsVertexIntegration>
                <PromptsOpenaiIntegration
                    :is-run-clicked="isRunClicked"
                    :selected-prompt="editablePrompt"
                    :filtered-models="filteredModels"
                    @update-setting="updateSetting"
                    :key="selectedIntegration.uid + editablePrompt?.id"
                    v-if="selectedIntegration.name === 'open_ai'">
                </PromptsOpenaiIntegration>
                <PromptsAzureOpenaiIntegration
                    :is-run-clicked="isRunClicked"
                    :selected-prompt="editablePrompt"
                    :filtered-models="filteredModels"
                    @update-setting="updateSetting"
                    :key="selectedIntegration.uid + editablePrompt?.id"
                    v-if="selectedIntegration.name === 'open_ai_azure'">
                </PromptsAzureOpenaiIntegration>
                <PromptsAiDialIntegration
                    :is-run-clicked="isRunClicked"
                    :selected-prompt="editablePrompt"
                    :filtered-models="filteredModels"
                    @update-setting="updateSetting"
                    :key="selectedIntegration.uid + editablePrompt?.id"
                    v-if="selectedIntegration.name === 'ai_dial'">
                </PromptsAiDialIntegration>
                <transition>
                    <prompts-tags-modal
                        v-if="showTagsModal"
                        :prompt="editablePrompt"
                        @update-tags="updateTags"
                        @close-modal="showTagsModal = false"
                    >
                    </prompts-tags-modal>
                </transition>
            </div>
        </div>
    </div>
    `
}

register_component('prompts-params', PromptsParams);
