const PromptFreeform = {
    props: [
        'selectedPrompt',
        'editablePrompt',
        'isPromptLoading',
        'isLatestVersion',
        'testInput',
        'testOutput',
        'isRunLoading',
        'isRunClicked',
    ],
    computed: {
        isDisableAddButton() {
            return !this.testOutput[0].content || !this.testInput ||
                this.testOutput[0].type === 'image' || this.testOutput.length > 1;
        },
        isInvalidTestInput() {
            return this.isRunClicked && !this.testInput
        },
        markdownParser() {
            return new markdownit()
        },
    },
    methods: {
        addEmptyParamsRow()  {
            $('#promptsParamsTable').bootstrapTable(
                'append',
                {id: Date.now() + Math.floor(Math.random() * 1000),"input": "", "output": "", "action": ""}
            )
        },
        convertToMarkdown(text) {
            return this.markdownParser.render(text)
        }
    },
    template: `
        <div class="flex-grow-1">
            <div class="mt-3">
             <p class="font-h6 font-bold text-gray-800" style="color: #32325D">EXAMPLES</p>
                <div class="position-relative" style="height: 116px" v-show="isPromptLoading">
                    <div class="layout-spinner">
                        <div class="spinner-centered">
                            <i class="spinner-loader__32x32"></i>
                        </div>
                    </div>
                </div>
                <div v-show="!isPromptLoading">
                    <table
                        id="promptsParamsTable"
                        class="w-100 table-transparent mb-2 params-table"
                        data-toggle="table"
                        data-unique-id="id"
                    >
                        <thead class="thead-light">
                            <tr>
                                <th data-field="id" data-visible="false"></th>
                                <th data-field="is_active"
                                    data-formatter="ParamsTable.cbxFormatter"
                                ></th>
                                <th data-field="input"
                                    data-formatter="ParamsTable.textareaFormatter"
                                >
                                    <span class="font-h6 font-semibold text-gray-800 mr-2">Input</span>
                                    <span class="font-h5 font-weight-400 text-capitalize text-gray-600">Input condition or question.</span>
                                </th>
                                <th data-field="output"
                                    data-formatter="ParamsTable.textareaFormatter"
                                >
                                    <span class="font-h6 font-semibold text-gray-800 mr-2">Output</span>
                                    <span class="font-h5 font-weight-400 text-capitalize text-gray-600">Input expected result.</span>
                                </th>
                                <th data-width="56" data-width-unit="px"
                                    data-field="action"
                                    data-formatter="ParamsTable.parametersDeleteFormatter"
                                ></th>
                            </tr>
                        </thead>
                        <tbody style="border-bottom: solid 1px #EAEDEF">
                        </tbody>
                    </table>
                    <button type="button" class="btn btn-sm btn-secondary mt-2"
                        :disabled="!isLatestVersion"
                        @click="addEmptyParamsRow">
                        <i class="fas fa-plus mr-2"></i>Add Parameter
                    </button>
                </div>
            </div>

            <div class="mt-3">
                <div class="d-flex justify-content-between mb-2">
                    <div class="d-flex align-items-center">
                        <p class="font-h6 font-bold text-gray-800 mr-4" style="color: #32325D">TEST</p>
                        <label class="custom-toggle mr-2" style="margin-top: 0">
                            <input type="checkbox"
                                   :checked="!editablePrompt.is_active_input"
                                   @click="$emit('update-cbx-input', $event)">
                            <span class="custom-toggle_slider round"></span>
                        </label>
                        <p class="font-h6 font-weight-400">Disable input</p>
                    </div>
                    <div class="d-flex">
                        <div v-if="editablePrompt.is_active_input">
                            <button :disabled="isDisableAddButton"
                                class="btn btn-secondary btn-icon__purple mr-2 d-flex cursor-pointer align-items-center" @click="$emit('add-test-result')">
                                    <i class="icon__18x18 icon-create-element mr-1"></i>
                                    <span>Add to examples</span>
                            </button>
                        </div>
                        <button type="button" :disabled="isRunLoading || isPromptLoading"
                            class="btn btn-basic d-flex align-items-center ml-2" @click="$emit('run-test')">
                            Run
                            <i v-if="isRunLoading" class="preview-loader__white ml-2"></i>
                        </button>
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
                    <table
                        class="w-100 table-transparent mb-2 params-table"
                        id="testResult">
                        <thead class="thead-light">
                            <tr>
                                <th data-field="inputTest"
                                    v-if="editablePrompt.is_active_input"
                                    >
                                    <span class="font-h6 font-semibold text-gray-800 mr-2">Input</span>
                                    <span class="font-h5 font-weight-400 text-capitalize text-gray-600">Input condition or question.</span>
                                </th>
                            </tr>
                        </thead>
                        <tbody style="border-bottom: solid 1px #EAEDEF">
                            <tr>
                                <td class="p-2" v-if="editablePrompt.is_active_input">
                                    <div class="custom-input" :class="{ 'invalid-input': isInvalidTestInput }">
                                        <textarea type="text" class="form-control form-control-alternative"
                                            rows="5"
                                            :value="testInput"
                                            @change="$emit('change-test-input', $event)">
                                        </textarea>
                                        <div class="invalid-tooltip invalid-tooltip-custom"></div>
                                    </div>
                                </td>
                            </tr>
                        </tbody>

                        <thead class="thead-light">
                            <tr>
                                <th data-field="outputTest">
                                    <span class="font-h6 font-semibold text-gray-800 mr-2">Output</span>
                                    <span class="font-h5 font-weight-400 text-capitalize text-gray-600">Input result.</span>
                                </th>
                            </tr>
                        </thead>
                        <tbody style="border-bottom: solid 1px #EAEDEF">
                            <tr v-for="message in testOutput">
                                <td class="p-2">
                                    <div v-if="message.type === 'image'" class="text-center">
                                        <img :src="message.content"/>
                                    </div>
                                    <div v-if="message.type === 'text'">
                                        <div 
                                            style="resize: vertical; height: 136px"
                                            v-html="convertToMarkdown(message.content)"
                                            class="prompt-chat form-control-alternative"
                                        >
                                        </div>
                                        <div class="invalid-tooltip invalid-tooltip-custom"></div>
                                    </div>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `
}