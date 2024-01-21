'use strict';
import { commHandler } from "./main.js";

export class ScreenManager{
    constructor(){
        ;
    }
    set(name, value){
        const data = {};
        data[name] = value;
        const payload = {
            set: data
        }
        commHandler.sendData(payload);
    }
    get(name, value){
        //Value here is not used yet, but could be useful?
        const data = {};
        data[name] = value;
        const payload = {
            get: data
        }
        commHandler.sendData(payload);
    }
}