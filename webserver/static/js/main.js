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
const commHandler = new CommHandler({wsUrl: "ws://localhost:8080/ws"})
// const commHandler = new CommHandler({wsUrl: "ws://raspberrypi:8080/ws"})

const screenParams = reactive({
    display_on: true,
    brightness: 0,
    display_dur: 20,
    images: [],
    display_mode: 'images',
    display_modes: [],
    run_snakes: false,
    nr_snakes: 7,
    food: 15,
    snakes_fps: 10
})

const inputField = defineComponent({
    template: "#input-field",
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
        watch(() => screenParams[props.param], (newVal, oldVal) => {
            checked.value = newVal === props.param;
        })
        return {
            onChange,
            checked
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
        'radio-btn': radioButton
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