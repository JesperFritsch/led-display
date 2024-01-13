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
const commHandler = new CommHandler({wsUrl: "ws://raspberrypi:8080/ws"});

const screenParams = reactive({
    display_on: true,
})

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
            screenManager.displayOn(checked.value);
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
    },
});
createApp(app).mount('#app');

export { commHandler, screenParams };