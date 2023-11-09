const PromptsRange = {
    props: {
        title: {},
        minValue: {
            default: 0,
        },
        maxValue: {
            default: 1,
        },
        step: {
            default: 1
        },
        modelValue: {},
    },
    emits: ['update:modelValue'],
    data() {
        return {
            randomWizardId: 'rangeId_' + Date.now() + Math.floor(Math.random() * 1000),
            randomInputId: 'inputId_' + Date.now() + Math.floor(Math.random() * 1000),
            noUiSliderData: null,
        }
    },
    mounted() {
        this.noUiSliderData = noUiSlider.create($(`#${this.randomWizardId}`)[0], {
            start: this.modelValue,
            connect: 'lower',
            range: {
                'min': this.minValue,
                'max': this.maxValue
            },
            step: this.step,
        });
        $(`#${this.randomInputId}`).on('change', (e) => {
            const inputtedNumber = +e.target.value;
            this.noUiSliderData.set(inputtedNumber);
        });
        const vm = this;
        this.noUiSliderData.on('update', function (values, handle) {
            const vuh = vm.step < 1 ? values[0] : parseInt(values[handle])
            $(`#${vm.randomInputId}`).val(vuh);
            vm.$emit('update:modelValue', +vuh)
        })
    },
    template: `
        <div>
            <label class="w-100 mb-0 font-h6 text-gray-500 text-uppercase">
                {{ title }}
            </label>
            <div class="d-flex">
                <div class="slider-holder w-100">
                    <div v-bind:id="randomWizardId"></div>
                </div>
                <div class="custom-input custom-input__sm ml-4">
                    <input type="number" class="custom-input input-wizard" v-bind:id="randomInputId">
                </div>
            </div>    
        </div>
    `
}

register_component('prompts-range', PromptsRange);