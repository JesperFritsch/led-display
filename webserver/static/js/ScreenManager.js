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
        if(commHandler === undefined){
            console.log("commHandler is not initialized yet");
            return;
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
        if(commHandler === undefined){
            console.log("commHandler is not initialized yet");
            return;
        }
        commHandler.sendData(payload);
    }
    action(name){
        const data = {};
        data[name] = true;
        const payload = {
            action: data
        }
        if(commHandler === undefined){
            console.log("commHandler is not initialized yet");
            return;
        }
        commHandler.sendData(payload);
    }
}