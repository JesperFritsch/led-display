'use strict';

import { screenParams } from "./main.js";
export class CommHandler{
    constructor(params){
        this.wsUrl = null;
        this.connection = null;
        this.parseParams(params);
        this.connect();
    }
    parseParams(params){
        if(!Object.keys(params).includes('wsUrl')){
            throw new Error('wsUrl is missing')
        }
        Object.assign(this, params);
    }
    connect(){
        console.log(`Connecting to :'${this.wsUrl}'`);
        this.connection = new WebSocket(this.wsUrl);
        this.connection.onmessage = this.receiveData.bind(this);
        this.connection.onopen = () => {
            this.sendData({get: {all: null}});
        }
    }
    is_connected(){
        return this.connection.readyState === WebSocket.OPEN;
    }
    receiveData(event){
        Object.assign(screenParams, JSON.parse(event.data));
        console.log(event.data);
    }
    sendData(data){
        if (!this.is_connected()){
            this.connect();
        }
        this.connection.send(JSON.stringify(data))
    }
}