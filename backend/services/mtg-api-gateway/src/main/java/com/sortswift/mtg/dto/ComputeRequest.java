package com.sortswift.mtg.dto;

import jakarta.validation.constraints.NotBlank;

import java.util.List;

public class ComputeRequest {

    @NotBlank
    private String jobType;
    private List<String> args;

    public String getJobType() {
        return jobType;
    }

    public void setJobType(String jobType) {
        this.jobType = jobType;
    }

    public List<String> getArgs() {
        return args;
    }

    public void setArgs(List<String> args) {
        this.args = args;
    }
}
