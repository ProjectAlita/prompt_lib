const PromptsModalCreate = {
    props: ['modalType', 'isModalLoading'],
    emits: ['close-create-modal', 'save-prompt', 'update-prompt'],
    data() {
        return {
            newPromptName: '',
            saveClicked: false,
        }
    },
    computed: {
        hasError() {
            return this.newPromptName.length < 3 && this.saveClicked;
        },
    },
    methods: {
        handleSubmit() {
            this.saveClicked = true;

            if (this.hasError) return;
            switch (this.modalType) {
                case 'create':
                    this.$emit('save-prompt', this.newPromptName);
                    break;
                case 'edit':
                    this.$emit('update-prompt', this.newPromptName);
                    break;
            }
        },
    },
    template: `
    <div class="modal-component">
        <div class="modal-card">
            <p class="font-bold font-h3 mb-4 text-capitalize">{{ modalType }} prompt</p>
            <div class="custom-input need-validation mb-4 w-100" :class="{'invalid-input': hasError}">
                <label for="promptName" class="font-semibold mb-1">Name</label>
                <input
                    id="promptName"
                    type="text"
                    v-model="newPromptName"
                    placeholder="Prompt name">
                <span class="input_error-msg">Prompt's name less than 3 letters</span>
            </div>
            <div class="d-flex justify-content-end">
                <button type="button" class="btn btn-secondary mr-2" 
                    @click="$emit('close-create-modal')">Cancel</button>
                <button
                    class="btn btn-basic mr-2 d-flex align-items-center"
                    @click="handleSubmit"
                >Save <i v-if="isModalLoading" class="preview-loader__white ml-2"></i></button>
            </div>
        </div>
    </div>
`
}