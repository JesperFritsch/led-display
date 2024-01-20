'use strict';
import { ScreenManager } from './ScreenManager.js';
import { CommHandler } from './CommHandler.js';
import {
    createApp,
    ref,
    defineComponent,
    defineProps,
    reactive,
    watch } from 'vue';

const screenManager = new ScreenManager();
const commHandler = new CommHandler({wsUrl: "ws://localhost:8080/ws"})
// const commHandler = new CommHandler({wsUrl: "ws://raspberrypi:8080/ws"})

const screenParams = reactive({
    display_on: true,
    brightness: 0,
    display_dur: 20
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
                screenManager[props.param](parseInt(textValue.value));
            }
        }
        watch(() => screenParams[props.param], (newVal, oldVal) => {
            console.log('asa')
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
            screenManager[props.param](checked.value);
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

const app = defineComponent({
    template: '#app-template',
    components: {
        'custom-checkbox': customCheckbox,
        'input-field': inputField
    },
});
createApp(app).mount('#app');

export { commHandler, screenParams };