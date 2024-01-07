'use strict';
import { commHandler } from "./main.js";

export class ScreenManager{
    constructor(){
        ;
    }
    screenOn(value){
        const data = {
            screenOn: value
        }
        commHandler.sendData(data);
    }
}