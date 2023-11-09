const PromptsTagsFilter = {
    props: ['selectedPrompt', 'allTags'],
    data() {
        return {
            inputText: '',
            btt: null,
            selectedTags: [],
            searchedName: '',
        }
    },
    mounted() {
        this.createInputsTags();
        this.addEventOnSearchName();
    },
    methods: {
        addEventOnSearchName() {
            $('#nameSearch').on('input', ({ target: { value }}) => {
                $('#prompts-aside-table').bootstrapTable('filterBy', {
                    name: value.toLowerCase()
                }, {
                    'filterAlgorithm': (row, filters) => {
                        if (filters) {
                            const isRowHasTags = (this.btt.getFullSelectedValues()).every(filteredTag => {
                                return row.tags.map(({ tag }) => tag).includes(filteredTag.title);
                            })
                            const isRowHasName = row.name.includes(filters.name);
                            return isRowHasTags && isRowHasName;
                        }
                    }
                })
                if (this.selectedPrompt.id) {
                    $('#prompts-aside-table').find(`[data-uniqueid='${this.selectedPrompt.id}']`).addClass('highlight');
                }
            });
        },
        createInputsTags() {
            this.$nextTick(() => {
                this.btt = BootstrapInputsTags.init("select#searchByTag", {
                    onInputChart: (text) => {
                        this.inputText = text;
                    },
                    onSelectItem: (item, inst) => {
                        this.filterPromptsByTags(this.btt.getFullSelectedValues());
                    },
                    onClearItem: (item, inst) => {
                        this.filterPromptsByTags(this.btt.getFullSelectedValues());
                    }
                });
            })
        },
        filterPromptsByTags(tags) {
            $('#prompts-aside-table').bootstrapTable('filterBy', {
                tags: tags
            }, {
                'filterAlgorithm': (row, filters) => {
                    if (filters) {
                        const isRowHasTags = filters.tags.every(filteredTag => {
                            return row.tags.map(({ tag }) => tag).includes(filteredTag.title);
                        })
                        const isRowHasName = row.name.includes(this.searchedName);
                        return isRowHasTags && isRowHasName;
                    }
                }
            })
            if (this.selectedPrompt.id) {
                $('#prompts-aside-table').find(`[data-uniqueid='${this.selectedPrompt.id}']`).addClass('highlight');
            }
        },
    },
    template: `
        <div class="px-4 mt-2">
            <div class="w-100">
                <p class="font-h6 font-semibold mb-1">Search by name</p>
                <div class="custom-input custom-input_search__sm custom-input__sm position-relative mb-2">
                    <input
                        id="nameSearch"
                        v-model="searchedName"
                        type="text"
                        placeholder="Prompt's name">
                    <img src="/design-system/static/assets/ico/search.svg" class="icon-search position-absolute">
                </div>
            </div>
            <p class="font-h6 font-semibold mb-1">Search by tag</p>
            <form class="needs-validation form-tags" novalidate onsubmit="event.preventDefault();">
                <select class="form-select"
                    id="searchByTag"
                    name="tags_show[]"
                    multiple
                    data-allow-new="true"
                    data-show-all-suggestions="true"
                    data-allow-clear="true">
                    <option disabled hidden value="">Type to search tag</option>
                    <option v-for="tag in allTags"
                        :key="tag.title"
                        :value="tag.title"
                        :selected="tag.selected"
                        :data-style-color="tag.hex">{{ tag.title }}</option>
                </select>
                <div class="invalid-feedback">Please select a valid tag.</div>
            </form>
        </div>
    `
}