`timescale 1ns/1ps
module tb_gf20;
    reg  [19:0] raw;
    wire [31:0] dut;
    reg  [31:0] expected;
    integer fd, r, pass, fail, total;
    reg exp_is_nan, dut_is_nan;
    gf_decode_param #(.N(20),.E(7),.M(12),.BIAS(63),.OUT_REG(0)) dut0 (
        .clk(1'b0),.rst_n(1'b1),.gf_in(raw),.fp32_out(dut),
        .is_nan_o(),.is_inf_o(),.is_zero_o(),.is_subnormal_o());
    initial begin
        fd=$fopen("/Users/playom/trinity-fpga/fpga/witness/gf_decode/build/vectors_gf20.txt","r");
        if(fd==0) begin $display("ERROR open"); $finish; end
        pass=0;fail=0;total=0;
        r=$fscanf(fd,"%h %h",raw,expected);
        while(r==2) begin
            #1;
            exp_is_nan=(expected[30:23]==8'hFF)&&(expected[22:0]!=0);
            dut_is_nan=(dut[30:23]==8'hFF)&&(dut[22:0]!=0);
            total=total+1;
            if((exp_is_nan&&dut_is_nan)||(!exp_is_nan&&(dut==expected))) pass=pass+1;
            else begin
                fail=fail+1;
                if(fail<=12) $display("MISMATCH raw=%h golden=%h dut=%h",raw,expected,dut);
            end
            r=$fscanf(fd,"%h %h",raw,expected);
        end
        $fclose(fd);
        $display("HW RESULT: %0d/%0d bit-exact (fails=%0d) [gf20]",pass,total,fail);
        if(fail==0) $display("PASS gf20"); else $display("FAIL gf20");
        $finish;
    end
endmodule
