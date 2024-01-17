'use strict';
import { commHandler } from "./main.js";

export class ScreenManager{
    constructor(){
        ;
    }
    sendMessage(name, value){
        const data = {};
        data[name] = value;
        commHandler.sendData(data);
    }
    display_on(value){
        this.sendMessage('display_on', value);
    }
    display_dur(value){
        this.sendMessage('display_dur', value);
    }
    brightness(value){
        this.sendMessage('brightness', value);
    }
}