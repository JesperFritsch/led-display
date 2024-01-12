'use strict';
import { commHandler } from "./main.js";

export class ScreenManager{
    constructor(){
        ;
    }
    displayOn(value){
        const data = {
            display_on: value
        }
        commHandler.sendData(data);
    }
}