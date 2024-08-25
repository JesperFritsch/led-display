'use strict';
import { ScreenManager } from './ScreenManager.js';
import { CommHandler } from './CommHandler.js';
import {
    createApp,
    ref,
    defineComponent,
    defineProps,
    reactive,
    watch,
    onMounted } from 'vue';

const screenManager = new ScreenManager();
// const commHandler = new CommHandler({wsUrl: "ws://localhost:8080/ws"})
const commHandler = new CommHandler({wsUrl: "ws://raspberrypi:8080/ws"})

const screenParams = reactive({
    display_on: null,
    brightness: null,
    display_dur: null,
    images: [],
    display_mode: null,
    display_modes: [],
    nr_snakes: null,
    food: null,
    food_decay: null,
    calc_timeout: null,
    snakes_fps: null,
    snake_maps: [],
    snake_map: null,
})

const inputField = defineComponent({
    template: "#input-field-template",
    props:{
        label: String,
        param: String
    },
    setup(props){
        const textValue = ref('');
        function onChange(){
            const value = textValue.value;
            if(!isNaN(value)){
                screenManager.set(props.param, parseInt(textValue.value));
            }
        }
        watch(() => screenParams[props.param], (newVal, oldVal) => {
            textValue.value = newVal;
        });
        return {
            onChange,
            textValue
        }
    }
});

const inputRange = defineComponent({
    template: "#input-range-template",
    props:{
        label: String,
        param: String,
        min: Number,
        max: Number,
        step: Number,
    },
    setup(props){
        const rangeValue = ref(props.modelValue || 0);
        function onChange(){
            console.log(rangeValue.value);
            screenManager.set(props.param, rangeValue.value);
        }
        watch(() => screenParams[props.param], (newVal, oldVal) => {
            rangeValue.value = newVal;
        });
        return {
            onChange,
            rangeValue
        }
    }
});

const customCheckbox = defineComponent({
    template: '#checkbox-template',
    props: {
        label: String,
        param: String
    },
    setup(props) {
        const checked = ref(true);
        function onChange(){
            checked.value = !checked.value;
            screenManager.set(props.param, checked.value);
        }
        watch(() => screenParams[props.param], (newVal, oldVal) => {
            checked.value = newVal;
        })
        return {
            onChange,
            checked
        }
    }
})

const cmdButton = defineComponent({
    template: '#cmd-btn-template',
    props: {
        label: String,
        cmd: String
    },
    setup(props){
        function onClick(){
            screenManager.set(props.cmd, true);
        }
        return {
            onClick
        }
    }
});

const toggleButton = defineComponent({
    template: '#toggle-btn-template',
    props: {
        label: String,
        param: String
    },
    setup(props){
        const toggled = ref(null);
        function toggle(){
            toggled.value = !toggled.value;
            screenManager.set(props.param, toggled.value);
        }
        watch(() => screenParams[props.param], (newVal, oldVal) => {
            toggled.value = newVal;
        })
        return {
            toggle,
            toggled
        }
    }
});

const imageButton = defineComponent({
    template: '#image-template',
    props: {
        img_name: String
    },
    setup(props){
        const image_path = 'images/' + props.img_name
        function onClick(){
            screenManager.set('image', props.img_name);
        }
        return {
            image_path,
            onClick
        }
    }
});

const radioButton = defineComponent({
    template: '#radio-btn-template',
    props: {
        label: String,
        param: String,
        group: String
    },
    setup(props){
        const checked = ref(false);
        function onChange(){
            screenManager.set(props.group, props.param);
        }
        watch(() => screenParams[props.group], (newVal, oldVal) => {
            checked.value = newVal === props.param;
        })
        return {
            onChange,
            checked
        }
    },
    mounted(){
        this.checked = screenParams[this.group] === this.param;
    }
});

const radioGroup = defineComponent({
    template: '#radio-group-template',
    components: {
        'radio-btn': radioButton
    },
    props: {
        groupName: String,
        options: Array
    },
    setup(props){
        const groupName = props.groupName;
        const options = ref(props.options)
        watch(() => props.options, (newVal) => {
            options.value = newVal;
        }, { immediate: true, deep: true });
        return {
            groupName,
            options
        };
    }
});


const dropdown = defineComponent({
    template: '#dropdown-template',
    props: {
        label: String,
        options: Array,
        param: String
    },
    setup(props){
        const selectedItem = ref('Default map');
        function onClick(e){
            selectedItem.value = e.target.innerText;
            screenManager.set(props.param, selectedItem.value);
        }
        watch(() => screenParams[props.param], (newVal, oldVal) => {
            selectedItem.value = newVal;
        })
        return {
            selectedItem,
            onClick
        }
    }
});

const app = defineComponent({
    template: '#app-template',
    components: {
        'custom-checkbox': customCheckbox,
        'input-field': inputField,
        'image-btn': imageButton,
        'cmd-btn': cmdButton,
        'toggle-btn': toggleButton,
        'radio-btn': radioButton,
        'radio-group': radioGroup,
        'input-range': inputRange,
        'dropdown-list': dropdown
    },
    setup(){
        return {screenParams}
    }
});
createApp(app).mount('#app');

export {
    commHandler,
    screenParams,
    imageButton,
    cmdButton,
    radioButton
};