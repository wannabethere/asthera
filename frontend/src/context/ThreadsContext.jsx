import React from "react";
import { createContext, useContext } from "react"

const ThreadContext = createContext();

export const ThreadsProvider = ({ children }) => {
    const [threads, setThreads] = React.useState([{
        sessionId: null,
        messages: [],
        name: 'Main Thread',
        pinned: false
    }]);
    const [currentThreadIndex, setCurrentThreadIndex] = React.useState(0);
    const [selectedItem, setSelectedItem] = React.useState('Collections');

    const value = {
        threads,
        setThreads,
        currentThreadIndex,
        setCurrentThreadIndex,
        selectedItem,
        setSelectedItem
    }

    return (
        <ThreadContext.Provider value={value}>
            {children}
        </ThreadContext.Provider>
    )
}

export const useThreads = () => {
    const contextThreads = useContext(ThreadContext);
    if (!contextThreads) {
        throw new Error('useThreads must be used within a ThreadsProvider');
    }
    return contextThreads;
}