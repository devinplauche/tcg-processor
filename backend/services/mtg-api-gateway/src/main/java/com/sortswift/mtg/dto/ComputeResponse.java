package com.sortswift.mtg.dto;

public class ComputeResponse {

    private final String status;
    private final String jobType;
    private final int exitCode;
    private final String output;

    public ComputeResponse(String status, String jobType, int exitCode, String output) {
        this.status = status;
        this.jobType = jobType;
        this.exitCode = exitCode;
        this.output = output;
    }

    public String getStatus() {
        return status;
    }

    public String getJobType() {
        return jobType;
    }

    public int getExitCode() {
        return exitCode;
    }

    public String getOutput() {
        return output;
    }
}
