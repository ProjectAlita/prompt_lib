const PromptChat = {
    props: ['editablePrompt', 'isPromptLoading', 'isLatestVersion', 'integrations', 'selectedIntegration', 'embedding_settings', 'isShowEmbedding'],
    data() {
        return {
            chat_history: [],
            newMessage: '',
            isRunLoading: false,
        }
    },
    watch: {
        'editablePrompt.id': function (newVal, oldVal) {
            if (!newVal) return
            this.cleatChat();
            this.newMessage = '';
        },
    },
    computed: {
        markdownParser() {
            return new markdownit()
        },
    },
    methods: {
        addEmptyParamsRow() {
            const newExample = {
                id: Date.now() + Math.floor(Math.random() * 1000),
                input: '',
                output: '',
                is_active: true,
            }
            if (this.editablePrompt.hasOwnProperty('examples')) {
                this.editablePrompt.examples.push(newExample);
            } else {
                this.editablePrompt.examples = [newExample];
            }
        },
        runChat() {
            this.$emit('run-chat');
            if (this.selectedIntegration.uid) {
                const integrationId = this.integrations.find(integration => integration.uid === this.selectedIntegration.uid);
                const chatHistory = [...this.chat_history];
                this.chat_history.push({
                    'role': 'user',
                    'content': this.newMessage,
                })
                this.$nextTick(() => {
                    this.scrollChat();
                })
                this.isRunLoading = true;
                const embeddingSetting = !!this.editablePrompt.embeddings && this.isShowEmbedding
                    ? this.embedding_settings
                    : null;
                const userMessage = this.newMessage;
                this.newMessage = '';
                ApiRunChat(this.editablePrompt, userMessage, chatHistory, integrationId.uid, embeddingSetting).then(data => {
                    this.chat_history.push({
                        'role': 'ai',
                        'content': data['messages'][0].content,
                    })
                    this.$nextTick(() => {
                        this.scrollChat();
                    })
                }).catch(err => {
                    showNotify('ERROR', err)
                }).finally(() => {
                    this.isRunLoading = false;
                })
            }
        },
        isAiRole(role) {
            return role === 'ai';
        },
        cleatChat() {
            this.chat_history = [];
        },
        deleteExample(exampleId) {
            if (exampleId < 1000000) {
                ApiDeleteExample(exampleId).then(() => {
                    showNotify('SUCCESS', 'Example delete.');
                })
            }
            this.editablePrompt.examples = this.editablePrompt.examples.filter(example => example.id !== exampleId);
        },
        checkExampleField(currentType, checkType, exampleId, {target}, fieldType) {
            const currentExample = this.editablePrompt.examples.find(example => example.id === exampleId);
            if (exampleId > 1000000) {
                if (fieldType === 'checkbox') return
                this.editablePrompt.examples.forEach(example => {
                    if (example.id === exampleId) {
                        example[currentType] = target.value;
                    }
                })
                if (currentExample[checkType]) {
                    ApiCreateExample(this.editablePrompt.id, currentExample.input, currentExample.output).then(data => {
                        showNotify('SUCCESS', `Example was created.`);
                        this.editablePrompt.examples.forEach(example => {
                            if (example.id === exampleId) {
                                example.id = data.id;
                            }
                        })
                    })
                }
            } else {
                if (fieldType === 'checkbox') {
                    ApiUpdateExampleField(this.editablePrompt.id, exampleId, currentExample.input, currentExample.output, target.checked).then(data => {
                        showNotify('INFO', `Example was updated.`);
                    })
                } else {
                    this.editablePrompt.examples.forEach(example => {
                        if (example.id === exampleId) {
                            example[currentType] = target.value;
                        }
                    })
                    ApiUpdateExampleField(this.editablePrompt.id, exampleId, currentExample.input, currentExample.output, currentExample.is_active).then(newExample => {
                        showNotify('INFO', `Example was updated.`);
                    })
                }
            }
        },
        scrollChat() {
            const elem = document.getElementById('chatContainer');
            elem.scrollTop = elem.scrollHeight;
        },
        convertToMarkdown(text) {
            return this.markdownParser.render(text)
        }
    },
    template: `
        <div class="flex-grow-1">
            <div class="mt-3">
                <p class="font-h6 font-bold text-gray-800" style="color: #32325D">CONVERSATION</p>
                <div class="position-relative" style="height: 116px" v-show="isPromptLoading">
                    <div class="layout-spinner">
                        <div class="spinner-centered">
                            <i class="spinner-loader__32x32"></i>
                        </div>
                    </div>
                </div>
                <div v-show="!isPromptLoading" class="mt-4">
                    <div class="d-flex gap-3 align-items-center border-top py-2" v-for="example in editablePrompt.examples">
                        <div class="d-flex justify-content-center w-12">
                            <label class="mb-0 d-flex align-items-center custom-checkbox">
                                <input 
                                    type="checkbox"
                                    :checked="example.is_active"
                                    @change="checkExampleField(null, null, example.id, $event, 'checkbox')">
                            </label>
                        </div>
                        <div class="flex-grow-1">
                            <div class="d-flex gap-3 align-items-center mb-2">
                                <p class="font-h6 font-weight-600 w-12 text-gray-600">USER</p>
                                <div class="custom-input w-100">
                                    <input type="text" class="form-control" 
                                        :value="example.input"
                                        @change="checkExampleField('input', 'output', example.id, $event, 'input')">
                                </div>
                            </div>
                            <div class="d-flex gap-3 align-items-center">
                                <p class="font-h6 font-weight-600 w-12">AI</p>
                                <div class="custom-input w-100">
                                    <input type="text" class="form-control" 
                                        :value="example.output"
                                        @change="checkExampleField('output', 'input', example.id, $event, 'input')">
                                </div>
                            </div>
                        </div>
                        <button type="button"
                            @click="deleteExample(example.id)"
                            class="btn btn-default btn-xs btn-table btn-icon__xs ml-1">
                            <i class="icon__18x18 icon-delete"></i>
                        </button>
                    </div>
                    <div class="pt-2 border-top">
                        <button type="button" class="btn btn-sm btn-secondary mt-2"
                            :disabled="!isLatestVersion"
                            @click="addEmptyParamsRow">
                            <i class="fas fa-plus mr-2"></i>Example
                        </button>
                    </div>
                </div>
            </div>
            <div class="mt-3">
                <div class="d-flex justify-content-between mb-2">
                    <div class="d-flex align-items-center">
                        <p class="font-h6 font-bold text-gray-800 mr-4" style="color: #32325D">CHAT</p>
                    </div>
                    <div class="d-flex">
                        <p class="font-h5 text-gray-700 cursor-pointer" @click="cleatChat">Clear conversation</p>
                    </div>
                </div>
                <div class="position-relative" style="height: 188px" v-if="isPromptLoading">
                    <div class="layout-spinner">
                        <div class="spinner-centered">
                            <i class="spinner-loader__32x32"></i>
                        </div>
                    </div>
                </div>
                <div v-else>
                    <div class="prompt-chat" id="chatContainer">
                        <div v-if="chat_history.length > 0" 
                            class="d-flex gap-3 align-items-center rounded-sm" :style="[ isAiRole(message.role) ? { 'background': '#F9FAFF'} : '' ]" 
                            v-for="message in chat_history">
                            <p class="font-h6 font-weight-600 p-3 text-uppercase" style="min-width: 4rem;"
                                :style="[ isAiRole(message.role) ? { 'color': '#6C44DD' } : { 'color': '#757F99' }]" v-html="convertToMarkdown(message.role)"/>
                            <div class="p-3" >
                                <div v-html="convertToMarkdown(message.content)" />
                            </div>
                        </div>
                        <div v-else class="h-100 d-flex flex-column align-items-center justify-content-center">
                            <i class="icon-chatting"></i>
                            <p class="font-h5 text-gray-500">Start a conversation</p>
                        </div>
                    </div>
                    <div class="d-flex prompt-input mt-2">
                        <input type="text"
                            v-model="newMessage"
                            @keyup.enter="runChat"
                            class="flex-grow-1 prompt-message" 
                            placeholder="Enter a prompt to start conversation">
                        <button type="button" :disabled="isRunLoading || isPromptLoading"
                            style="padding: 4px 9px 4px 9px;"
                            class="btn btn-basic d-flex align-items-center ml-2" @click="runChat">
                            <i v-if="isRunLoading" class="preview-loader__white"></i>
                            <i v-else class="icon__white icon__14x14 icon-sent__message"></i>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `
}