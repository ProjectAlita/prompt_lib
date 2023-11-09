const PromptsTagsModal = {
    props: ['prompt'],
    data() {
        return {
            selectedColor: '#5933c6',
            btt: null,
            selectedTags: [],
            inputText: "",
            allTags: [],
            isLoading: false,
            dataLoaded: false,
        }
    },
    computed: {
        isUnCompletedTag() {
            return this.inputText.length;
        },
    },
    mounted() {
        this.fetchData()
    },
    methods: {
        fetchData() {
            Promise.all([fetchPromptTagsAPI(this.prompt.id), fetchTagsAPI()]).then(res => {
                const allTags = res[1];
                const currentTags = res[0];
                this.calculateTags(currentTags, allTags);
                this.dataLoaded = true;
                this.$nextTick(() => {
                    this.createColorPicker();
                    this.createInputsTags();
                })
            })
        },
        calculateTags(currentTags, allTags) {
            const currentTagsTitle = currentTags.map(tag => tag.tag)
            this.selectedTags = allTags.map(tag => ({
                title: tag.tag,
                hex: tag.color,
                selected: currentTagsTitle.includes(tag.tag),
            }))
        },
        createColorPicker() {
            Coloris({
                el: '#coloris',
                themeMode: 'light',
                onChange: (color) => {
                    this.selectedColor = color;
                    this.btt.changeColor(this.selectedColor)
                },
                swatches: [
                    '#5933c6',
                    '#29B8F5',
                    '#2bd48d',
                    '#EFE482',
                    '#F89033',
                    '#f32626',
                ],
            });
        },
        createInputsTags() {
            this.$nextTick(() => {
                this.btt = BootstrapInputsTags.init("select[multiple]", {
                    onInputChart: (text) => {
                        this.inputText = text;
                    },
                    selectedColor: this.selectedColor,
                });
            })
        },
        handleSubmit() {
            const newTags = this.formatterTags(this.btt.getFullSelectedValues());
            const uniqueValues = new Set(newTags.map(v => v.tag.toLowerCase()));
            if (uniqueValues.size < newTags.length) {
                showNotify('ERROR', `Don't use the duplicated name`);
                return;
            }
            this.isLoading = true;
            updatePromptTagsAPI(newTags, this.prompt.id).then(data => {
                showNotify('SUCCESS', `Tags updated.`)
                $("#prompts-aside-table").bootstrapTable('updateByUniqueId', {
                    id: this.prompt.id,
                    row: {
                        name: this.prompt.name,
                        tags: newTags,
                    }
                })
                $('#prompts-aside-table tbody tr').each((i, item) => {
                    const uniqId = $(item).attr('data-uniqueid')
                    if (+uniqId === this.prompt.id) {
                        $(item).addClass('highlight')
                    }
                })
            }).catch(e => {
                showNotify('ERROR', `error: ${e}`);
            }).finally(() => {
                this.$emit('update-tags', newTags);
                vueVm.registered_components['prompts-list-aside'].fetchTags();
                this.isLoading = false;
                this.closeModal()
            })
        },
        formatterTags(tags) {
            return tags.map(tag => ({
                tag: tag.title,
                color: tag.hex,
            }))
        },
        closeModal() {
            this.$emit('close-modal')
        }
    },
    template: `
        <div class="modal fade show d-block" id="tagsModal" tabindex="-1" aria-labelledby="exampleModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <p class="modal-title font-h3" id="exampleModalLabel">Manage Tags</p>
                        <button type="button" class="close" @click="closeModal" data-dismiss="modal" aria-label="Close">
                            <span aria-hidden="true"><i class="icon__16x16 icon-close__16"></i></span>
                        </button>
                    </div>
                    <div class="modal-body" v-if="dataLoaded">
                        <div class="d-flex align-items-center mb-2">
                            <div class="square">
                                <input type="text" id="coloris" class="square" :value="selectedColor">
                            </div>
                            <p class="font-h5 ml-2">Pick color before adding tag</p>
                        </div>
                        <form class="needs-validation form-tags" novalidate onsubmit="event.preventDefault();">
                            <select class="form-select"
                                id="validationTagsShow"
                                name="tags_show[]"
                                multiple
                                data-allow-new="true"
                                data-show-all-suggestions="true"
                                data-allow-clear="true">
                                <option disabled hidden value="">Type to search or create tag</option>
                                <option v-for="tag in selectedTags"
                                    :key="tag.title"
                                    :value="tag.title"
                                    :selected="tag.selected"
                                    :data-style-color="tag.hex">{{ tag.title }}</option>
                            </select>
                            <div class="invalid-feedback">Please select a valid tag.</div>
                        </form>
                    </div>
                    <div v-else style="height: 128px" class="d-flex justify-content-center align-items-center">
                        <i class="preview-loader"></i>
                    </div>
                    <div class="d-flex justify-content-end p-4">
                        <button type="button" class="btn btn-secondary" data-dismiss="modal" @click="closeModal">Close</button>
                        <button class="btn btn-basic d-flex align-items-center ml-2" 
                            :disabled="isUnCompletedTag"
                            @click="handleSubmit">Save
                            <i v-if="isLoading" class="preview-loader__white ml-2"></i>
                        </button>
                    </div>
                </div>
            </div>
        </div>
        <div class="modal-backdrop fade show"></div>
    `
}