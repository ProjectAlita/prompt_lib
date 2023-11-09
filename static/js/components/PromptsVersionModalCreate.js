const PromptsVersionModalCreate = {
    props: ['modalVersionType', 'isVersionModalLoading'],
    data() {
        return {
            newVersionName: '',
            saveClicked: false,
        }
    },
    computed: {
        hasError() {
            return this.newVersionName.length < 3 && this.saveClicked;
        },
        nameAlreadyExists() {
            const promptVersions = vueVm.registered_components['prompts-params'].promptVersions;
            return promptVersions.map(v => v.version).includes(this.newVersionName);
        }
    },
    methods: {
        handleSubmit() {
            this.saveClicked = true;
            if (this.hasError || this.nameAlreadyExists) return;
            switch (this.modalVersionType) {
                case 'create':
                    this.$emit('save-version', this.newVersionName);
                    break;
                case 'edit':
                    this.$emit('update-version', this.newVersionName);
                    break;
            }
        },
    },
    template: `
    <div class="modal-component">
        <div class="modal-card">
            <p class="font-bold font-h3 mb-4 text-capitalize">{{ modalVersionType }} version</p>
            <div class="custom-input need-validation mb-4 w-100" :class="{'invalid-input': hasError}">
                <label for="versionName" class="font-semibold mb-1">Name</label>
                <input
                    id="versionName"
                    type="text"
                    v-model="newVersionName"
                    placeholder="Version name">
                <span class="input_error-msg">Version's name less than 3 letters</span>
                <span v-if="nameAlreadyExists" class="mt-1 d-block" style="color: var(--error); font-size: 12px">This name already exists.</span>
            </div>
            <div class="d-flex justify-content-end">
                <button type="button" class="btn btn-secondary mr-2" 
                    @click="$emit('close-create-version-modal')">Cancel</button>
                <button
                    class="btn btn-basic mr-2 d-flex align-items-center"
                    @click="handleSubmit"
                    :disabled="nameAlreadyExists || hasError"
                >Save <i v-if="isVersionModalLoading" class="preview-loader__white ml-2"></i></button>
            </div>
        </div>
    </div>
`
}
