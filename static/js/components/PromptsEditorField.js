const PromptsEditorField = {
    props: {
        'modelValue': '',
        'title': '',
        'editablePrompt': '',
    },
    emits: ['update:modelValue'],
    data() {
        return {
            showEditor: false,
            MAX_VALUES: 256,
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
        saveDesc() {
            if (this.hasError(this.modelValue)) {
                return;
            }
            this.loading = true;
            ApiUpdatePrompt(this.editablePrompt).then(data => {
                this.$emit('update:modelValue', this.modelValue);
                showNotify('SUCCESS', `${this.title} updated.`);
                this.showEditor = false;
            }).finally(() => {
                this.loading = false;
            });
        },
        hasError(value) {
            if (!value) return false
            return value.length > this.MAX_VALUES;
        },
        closeEditor() {
            this.$emit('update:modelValue', this.initValue);
            this.showEditor = false;
        },
    },
    template: `
        <div class="mb-3">
            <div class="d-flex flex-column align-items-start">
                <div class="d-flex justify-content-between mb-1 align-items-center">
                    <p class="font-h6 font-bold font-uppercase text-gray-700">{{ title }}</p>
                    <button type="button"
                            style="min-width: 24px"
                            class="btn btn-default btn-xs btn-table btn-icon__xs edit_user ml-2" 
                            @click="openEditDesc" 
                            data-toggle="tooltip" 
                            data-placement="top">
                            <i class="icon__18x18 icon-edit"></i>
                    </button>
                </div>
                <span class="mr-2" v-if="!showEditor">{{ modelValue }}</span>
            </div>
            <div v-if="showEditor" class="d-flex justify-content-end align-items-center">
                <div class="custom-input flex-grow-1 need-validation" :class="{'invalid-input': hasError(modelValue)}"
                    :data-valid="hasError(modelValue)">
                    <textarea rows="2" class="form-control" 
                    :value="modelValue" @input="updateField">{{ modelValue }}</textarea>
                    <span class="input_error-msg font-h6 font-weight-400 text-right">{{ fieldLength }}/256</span>
                </div>
                <div>
                    <button class="btn btn-success__custom btn-xs btn-icon__xs ml-2 mb-2" @click="saveDesc"
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