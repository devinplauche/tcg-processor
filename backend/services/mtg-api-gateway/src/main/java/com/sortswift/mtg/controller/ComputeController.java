package com.sortswift.mtg.controller;

import com.sortswift.mtg.dto.ComputeRequest;
import com.sortswift.mtg.dto.ComputeResponse;
import com.sortswift.mtg.service.PythonComputeService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/compute")
public class ComputeController {

    private final PythonComputeService pythonComputeService;

    public ComputeController(PythonComputeService pythonComputeService) {
        this.pythonComputeService = pythonComputeService;
    }

    @PostMapping("/run")
    public ResponseEntity<ComputeResponse> runCompute(@Valid @RequestBody ComputeRequest request) {
        try {
            ComputeResponse response = pythonComputeService.runJob(request.getJobType(), request.getArgs());
            HttpStatus status = response.getExitCode() == 0 ? HttpStatus.OK : HttpStatus.BAD_REQUEST;
            return ResponseEntity.status(status).body(response);
        } catch (IllegalArgumentException ex) {
            return ResponseEntity.badRequest().body(new ComputeResponse(
                    "FAILED",
                    request.getJobType(),
                    400,
                    ex.getMessage()
            ));
        } catch (Exception ex) {
            return ResponseEntity.internalServerError().body(new ComputeResponse(
                    "FAILED",
                    request.getJobType(),
                    500,
                    ex.getMessage()
            ));
        }
    }
}
