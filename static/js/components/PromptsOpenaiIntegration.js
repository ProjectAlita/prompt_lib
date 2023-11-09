const PromptsOpenaiIntegration = {
    props: ['selectedPrompt', 'isRunClicked', 'filteredModels'],
    components: {
        'prompts-range': PromptsRange,
    },
    data() {
        return {
            editableIntegrationSetting: {
                temperature: 0,
                max_tokens: 1,
                top_p: 0,
                model: ""
            },
            isComponentMounted: false,
            tokens_limit: 32000,
        }
    },
    computed: {
        responsiveTableHeight() {
            return `${(window.innerHeight - 270)}px`;
        },
        isInvalid() {
            return this.isRunClicked && !this.editableIntegrationSetting.model_name
        },
        selectedModel() {
            return this.filteredModels.find(model => model.id === this.editableIntegrationSetting.model_name);
        },
    },
    mounted() {
        if (this.selectedPrompt.model_settings) {
            this.editableIntegrationSetting = { ...this.selectedPrompt.model_settings };
            this.isComponentMounted = true;
        }
        this.$nextTick(() => {
            $('#selectModel').val(this.editableIntegrationSetting.model_name).selectpicker('refresh');
        })
    },
    watch: {
        editableIntegrationSetting: {
            handler: function (newVal, oldVal) {
                this.$emit('update-setting', newVal)
            },
            deep: true
        },
        selectedModel(newVal) {
            if (newVal) {
                this.tokens_limit = newVal.token_limit;
            } else {
                this.tokens_limit = 32000; // default value
            }
          },
    },
    template: `
        <div>
            <div class="mt-4" v-if="isComponentMounted">
                <div class="select-validation mt-4 mb-4" :class="{ 'invalid-input': isInvalid }">
                    <p class="font-h5 font-semibold mb-1">Select model</p>
                    <select id="selectModel" class="selectpicker bootstrap-select__b displacement-ml-4 bootstrap-select__b-sm"
                        v-model="editableIntegrationSetting.model_name"
                        data-size="8"
                        data-style="btn">
                        <option v-for="model in filteredModels" :value="model.id">{{ model.name }}</option>
                    </select>
                </div>
                <prompts-range
                    @register="$root.register"
                    instance_name="prompts-range"
                    title="temperature"
                    :step="0.05"
                    :minValue="0"
                    :maxValue="1"
                    v-model:modelValue="editableIntegrationSetting.temperature"
                ></prompts-range>
                <prompts-range
                    @register="$root.register"
                    instance_name="prompts-range"
                    title="Token limit"
                    :step="1"
                    :minValue="1"
                    :maxValue="tokens_limit"
                    :key="editableIntegrationSetting.model_name"
                    v-model:modelValue="editableIntegrationSetting.max_tokens"
                ></prompts-range>
                <prompts-range
                    @register="$root.register"
                    instance_name="prompts-range"
                    title="Top-P"
                    :step="0.05"
                    :minValue="0"
                    :maxValue="1"
                    v-model:modelValue="editableIntegrationSetting.top_p"
                ></prompts-range>
            </div>
        </div>
    `
}
