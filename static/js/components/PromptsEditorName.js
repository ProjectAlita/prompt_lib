const PromptsEditorName = {
    props: {
        'modelValue': '',
        'editablePrompt': '',
    },
    emits: ['update:modelValue'],
    data() {
        return {
            showEditor: false,
            MIN_VALUES: 3,
            loading: false,
            initValue: '',
        }
    },
    computed: {
        fieldLength() {
            return this.modelValue?.length ?? 0
        }
    },
    mounted() {
        this.initValue = this.modelValue;
    },
    methods: {
        updateField({ target: { value }}) {
            this.$emit('update:modelValue', value);
        },
        openEditDesc() {
            this.showEditor = !this.showEditor;
        },
        closeEditor() {
            this.$emit('update:modelValue', this.initValue);
            this.showEditor = false;
        },
        saveDesc() {
            if (this.hasError(this.modelValue)) {
                return;
            }
            this.loading = true;
            updatePromptNameAPI(this.editablePrompt.id, this.modelValue).then(data => {
                this.$emit('update:modelValue', this.modelValue);
                showNotify('SUCCESS', `Prompt name updated.`);
                this.showEditor = false;
                $("#prompts-aside-table").bootstrapTable('updateByUniqueId', {
                    id: this.editablePrompt.id,
                    row: {
                        name: this.editablePrompt.name,
                        tags: this.editablePrompt.tags,
                    }
                })
                $('#prompts-aside-table tbody tr').each((i, item) => {
                    const uniqId = $(item).attr('data-uniqueid')
                    if (+uniqId === this.editablePrompt.id) {
                        $(item).addClass('highlight')
                    }
                })
            }).finally(() => {
                this.loading = false;
            });
        },
        hasError(value) {
            return value.length < this.MIN_VALUES;
        },
    },
    template: `
        <div>
            <div class="d-flex justify-content-between" v-if="!showEditor">
                <p class="font-h5 font-bold font-uppercase mb-1 flex-grow-1">
                    <span>{{ modelValue }}</span>
                </p>
                <button type="button"
                    style="min-width: 24px"
                    class="btn btn-default btn-xs btn-table btn-icon__xs ml-2" 
                    @click="openEditDesc" 
                    data-toggle="tooltip" 
                    data-placement="top">
                    <i class="icon__18x18 icon-edit"></i>
                </button>
            </div>
            <div v-if="showEditor" class="d-flex justify-content-end">
                <div class="custom-input flex-grow-1 need-validation" :class="{'invalid-input': hasError(modelValue)}"
                    :data-valid="hasError(modelValue)">
                    <input rows="2" class="form-control" 
                    :value="modelValue" @input="updateField">
                    <span class="input_error-msg font-h6 font-weight-400 text-right">{{ fieldLength }}/3</span>
                </div>
                <div class="d-flex" style="padding-top: 6px">
                    <button class="btn btn-success__custom btn-xs btn-icon__xs ml-2" @click="saveDesc"
                        :disabled="hasError(modelValue)">
                        <i class="preview-loader__white" v-if="loading"></i>
                        <i v-else class="icon__16x16 icon-check__white"></i>
                    </button>
                    <button class="btn btn-secondary btn-xs btn-icon__xs ml-2" 
                        @click="closeEditor">
                        <i class="icon__16x16 icon-close__16"></i>
                    </button>
                </div>
            </div>   
        </div> 
        
    `
}