// One supergolden step -- the third degree-3 sibling of phi_step and plastic_step.
//
// psi is the real root of psi^3 = psi^2 + 1 (psi = 1.465571231876768...), the
// "supergolden ratio". Representing a value as a + b*psi + c*psi^2,
//   psi(a + b psi + c psi^2) = a psi + b psi^2 + c psi^3
//                            = a psi + b psi^2 + c(psi^2 + 1)
//                            = c + a psi + (b+c) psi^2
// so the map is (a,b,c) -> (c, a, b+c): ONE addition and three registers, the
// same cost as the plastic number and one register more than phi.
//
// psi and the plastic number rho sit on either side of the 5-bit ladder result:
// both are one-adder degree-3 scales, psi coarser (1.4656) than rho (1.3247)
// and both finer than phi (1.6180). The arithmetic cost is identical, so the
// choice between them is a question about the network, not about the hardware.
`default_nettype none
module supergold_step #(parameter integer W = 32)(
    input  wire                clk,
    input  wire signed [W-1:0] a, b, c,
    output reg  signed [W-1:0] oa, ob, oc
);
    always @(posedge clk) begin
        oa <= c;
        ob <= a;
        oc <= b + c;
    end
endmodule
