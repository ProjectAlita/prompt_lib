const PromptsListAside = {
    components: {
        ImportPromptButton,
        PromptsTagsFilter,
    },
    props: ['selectedPrompt'],
    data() {
        return {
            isTagsLoaded: false,
            allTags: [],
            windowHeight: window.innerHeight,
        }
    },
    computed: {
        responsiveAsideHeight() {
            return `${(this.windowHeight - 95)}px`;
        },
        responsiveTableHeight() {
            return `${(this.windowHeight - 371)}px`;
        }
    },
    mounted() {
        this.fetchTags();
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
        fetchTags() {
            this.$nextTick(() => {
                this.isTagsLoaded = false;
                fetchTagsAPI().then(res => {
                    this.allTags = res.map(tag => ({
                        title: tag.tag,
                        hex: tag.color,
                        selected: false,
                    }));
                    this.isTagsLoaded = true;
                })
            })
        },
    },
    template: `
        <aside class="card card-table-sm" style="min-width: 340px; width: 340px" :style="{'height': responsiveAsideHeight}">
            <div class="p-4 d-flex justify-content-between">
                <div>
                    <p class="font-h4 font-bold">Prompts</p>
                </div>
                <div>
                    <div class="d-flex justify-content-end">
                        <ImportPromptButton></ImportPromptButton>
                        <div class="dropdown left dropdown_action mr-2">
                            <button class="btn btn-sm btn-icon__sm dropdown-toggle btn-secondary"
                                    role="button"
                                    id="dropdownMenuAction"
                                    data-toggle="dropdown"
                                    aria-expanded="false">
                                <i class="fa fa-plus"></i>
                            </button>
                            <ul class="dropdown-menu" aria-labelledby="dropdownMenuAction">
                                <li class="px-3 py-1 font-weight-500">Create</li>
                                <li class="dropdown-item" @click="$emit('open-create-modal', 'freeform')">
                                    <span class="pl-2">Completion prompt</span></li>
                                <li class="dropdown-item" @click="$emit('open-create-modal', 'chat')">
                                    <span class="pl-2">Chat prompt</span>
                                </li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
            <PromptsTagsFilter
                :key="allTags"
                v-if="isTagsLoaded"
                :selectedPrompt="selectedPrompt"
                :allTags="allTags">
            
            </PromptsTagsFilter>
            <div class="card-body pb-4" style="padding-top: 0">
                <table class="table table-borderless table-fix-thead"
                    id="prompts-aside-table"
                    data-toggle="table"
                    data-unique-id="id">
                    <thead class="thead-light bg-transparent">
                        <tr>
                            <th data-visible="false" data-field="id">index</th>
                            <th data-sortable="true" data-field="name" data-width="40" data-width-unit="%" class="cut-text">NAME</th>
                            <th scope="col" data-sortable="false" data-field="tags" data-formatter="ParamsTable.tagFormatter">Tags</th>
                            <th data-width="56" data-formatter='<div class="d-none justify-content-end">
                                    <button class="btn btn-default btn-xs btn-table btn-icon__xs prompt_delete"><i class="icon__18x18 icon-delete"></i></button>
                                </div>'
                                data-events="promptAsideEvents">
                            </th>
                        </tr>
                    </thead>
                    <tbody :style="{'height': responsiveTableHeight}">
                    </tbody>
                </table>
            </div>
        </aside>
    `
}

var promptAsideEvents = {
    "click .prompt_delete": function (e, value, row, index) {
        e.stopPropagation();
        const vm = vueVm.registered_components.prompts;
        vm.openConfirm();
    },
}

register_component('prompts-list-aside', PromptsListAside);
